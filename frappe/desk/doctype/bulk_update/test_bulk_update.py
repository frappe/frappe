# Copyright (c) 2023, Frappe Technologies and Contributors
# See LICENSE

import time

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.desk.doctype.bulk_update.bulk_update import submit_cancel_or_update_docs
from frappe.tests import IntegrationTestCase, timeout
from frappe.tests.utils.test_capabilities import TestService, requires_test_service


class TestBulkUpdate(IntegrationTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls.doctype = new_doctype(is_submittable=1, custom=1).insert().name
		cls.child_doctype = new_doctype(istable=1, custom=1).insert().name
		# Schema fixtures must exist before worker processes load their documents.
		frappe.db.commit()  # nosemgrep
		for _ in range(50):
			frappe.new_doc(cls.doctype, some_fieldname=frappe.mock("name")).insert()
		# Workers have their own database connections, so publish the fixtures
		# and release SQLite's single writer slot before a job is enqueued.
		frappe.db.commit()  # nosemgrep

	@classmethod
	def tearDownClass(cls) -> None:
		# Committed fixtures cannot be removed by the test framework's rollback.
		try:
			for doctype in (cls.doctype, cls.child_doctype):
				if frappe.db.exists("DocType", doctype):
					frappe.delete_doc("DocType", doctype, force=True)
			frappe.db.commit()  # nosemgrep
		finally:
			super().tearDownClass()

	@timeout()
	def wait_for_assertion(self, assertion):
		"""Wait till an assertion becomes True"""
		while True:
			if assertion():
				break
			time.sleep(0.2)

	@requires_test_service(TestService.BACKGROUND_WORKER)
	def test_bulk_submit_in_background(self):
		unsubmitted = frappe.get_all(self.doctype, {"docstatus": 0}, limit=5, pluck="name")
		failed = submit_cancel_or_update_docs(self.doctype, unsubmitted, action="submit")
		self.assertEqual(failed, [])

		def check_docstatus(docs, status):
			frappe.db.rollback()
			matching_docs = frappe.get_all(
				self.doctype, {"docstatus": status, "name": ("in", docs)}, pluck="name"
			)
			return set(matching_docs) == set(docs)

		unsubmitted = frappe.get_all(self.doctype, {"docstatus": 0}, limit=20, pluck="name")
		submit_cancel_or_update_docs(self.doctype, unsubmitted, action="submit")

		self.wait_for_assertion(lambda: check_docstatus(unsubmitted, 1))

		submitted = frappe.get_all(self.doctype, {"docstatus": 1}, limit=20, pluck="name")
		submit_cancel_or_update_docs(self.doctype, submitted, action="cancel")
		self.wait_for_assertion(lambda: check_docstatus(submitted, 2))

	@requires_test_service(TestService.BACKGROUND_WORKER)
	def test_bulk_update_parent_fields(self):
		docnames = frappe.get_all(self.doctype, {"docstatus": 0}, limit=5, pluck="name")
		failed = submit_cancel_or_update_docs(
			self.doctype, docnames, action="update", data={"some_fieldname": "_Test Sync"}
		)
		self.assertEqual(failed, [])

		def check_field_values(docs, expected):
			frappe.db.rollback()
			values = frappe.get_all(self.doctype, {"name": ["in", docs]}, ["name", "some_fieldname"])
			return all(v.some_fieldname == expected for v in values)

		docnames_bg = frappe.get_all(self.doctype, {"docstatus": 0}, limit=20, pluck="name")
		submit_cancel_or_update_docs(
			self.doctype, docnames_bg, action="update", data={"some_fieldname": "_Test Background"}
		)

		self.wait_for_assertion(lambda: check_field_values(docnames_bg, "_Test Background"))

	@requires_test_service(TestService.BACKGROUND_WORKER)
	def test_bulk_update_child_fields(self):
		doctype_doc = frappe.get_doc("DocType", self.doctype)
		doctype_doc.append(
			"fields", {"fieldname": "child_table", "fieldtype": "Table", "options": self.child_doctype}
		)
		doctype_doc.save()
		# The worker must see the child table added by this schema change.
		frappe.db.commit()  # nosemgrep

		existing_docs = frappe.get_all(self.doctype, {"docstatus": 0}, pluck="name")
		for docname in existing_docs:
			doc = frappe.get_doc(self.doctype, docname)
			doc.append("child_table", {"some_fieldname": "_Test Child Value"})
			doc.save()
		# Publish child rows before the background update reads them.
		frappe.db.commit()  # nosemgrep

		update_data = {
			"child_table_updates": {
				self.child_doctype: {"some_fieldname": "_Test Child Updated"},
			}
		}

		def check_child_field(docs, expected):
			frappe.db.rollback()
			for docname in docs:
				doc = frappe.get_doc(self.doctype, docname)
				if not doc.child_table or doc.child_table[0].some_fieldname != expected:
					return False
			return True

		docnames = frappe.get_all(self.doctype, {"docstatus": 0}, limit=5, pluck="name")
		failed = submit_cancel_or_update_docs(self.doctype, docnames, action="update", data=update_data)
		self.assertEqual(failed, [])

		docnames_bg = frappe.get_all(self.doctype, {"docstatus": 0}, limit=20, pluck="name")
		submit_cancel_or_update_docs(self.doctype, docnames_bg, action="update", data=update_data)
		self.wait_for_assertion(lambda: check_child_field(docnames_bg, "_Test Child Updated"))

	def test_bulk_update_conditions(self):
		"""Test the whitelisted bulk update method"""
		todo_names = []
		for i in range(5):
			doc = frappe.get_doc(
				{
					"doctype": "ToDo",
					"description": f"Bulk Update Status Test {i}",
					"status": "Open" if i < 3 else "Closed",
				}
			).insert()
			todo_names.append(doc.name)

		try:
			condition_json = frappe.as_json({"status": "Open", "name": ["in", todo_names]})

			bulk_upd = frappe.get_doc(
				{
					"doctype": "Bulk Update",
					"document_type": "ToDo",
					"field": "status",
					"update_value": "Closed",
					"condition": condition_json,
					"limit": 5,
				}
			)

			bulk_upd.bulk_update()

			updated_docs = frappe.get_all("ToDo", filters={"name": ["in", todo_names]}, fields=["status"])

			for doc in updated_docs:
				self.assertEqual(doc.status, "Closed")

			remaining_open_count = frappe.db.count("ToDo", {"name": ["in", todo_names], "status": "Open"})
			self.assertEqual(remaining_open_count, 0)

		finally:
			for name in todo_names:
				frappe.delete_doc("ToDo", name)
			# bulk_update can commit, so its durable fixtures need durable cleanup.
			frappe.db.commit()  # nosemgrep
