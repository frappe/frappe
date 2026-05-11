# Copyright (c) 2023, Frappe Technologies and Contributors
# See LICENSE

import time

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.desk.doctype.bulk_update.bulk_update import submit_cancel_or_update_docs
from frappe.tests.utils import FrappeTestCase, timeout


class TestBulkUpdate(FrappeTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls.doctype = new_doctype(is_submittable=1, custom=1).insert().name
		frappe.db.commit()
		for _ in range(50):
			frappe.new_doc(cls.doctype, some_fieldname=frappe.mock("name")).insert()

	@timeout()
	def wait_for_assertion(self, assertion):
		"""Wait till an assertion becomes True"""
		while True:
			if assertion():
				break
			time.sleep(0.2)

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
			frappe.db.commit()
