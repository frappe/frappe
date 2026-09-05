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
		frappe.db.commit()

		existing_docs = frappe.get_all(self.doctype, {"docstatus": 0}, pluck="name")
		for docname in existing_docs:
			doc = frappe.get_doc(self.doctype, docname)
			doc.append("child_table", {"some_fieldname": "_Test Child Value"})
			doc.save()
		frappe.db.commit()

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
			frappe.db.commit()


class TestBulkAssignRoles(IntegrationTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls.test_users = []
		for i in range(2):
			email = f"bulk_role_test_{i}@example.com"
			if frappe.db.exists("User", email):
				frappe.delete_doc("User", email, force=True)
				frappe.db.commit()

			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": f"BulkRoleTest{i}",
					"send_welcome_email": 0,
					"roles": [{"role": "Desk User"}],
				}
			)
			user.insert(ignore_permissions=True)
			frappe.db.commit()  # ← commit after each insert

			# verify it was created
			if not frappe.db.exists("User", email):
				frappe.throw(f"Failed to create test user {email}")

			cls.test_users.append(email)

		frappe.db.set_value("User", "Administrator", "bulk_actions", 1)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls) -> None:
		for email in cls.test_users:
			frappe.delete_doc("User", email, force=True)
		frappe.db.commit()
		super().tearDownClass()

	def test_bulk_assign_roles_as_system_manager(self):
		"""System Manager can bulk assign roles to multiple users"""
		from frappe.desk.doctype.bulk_update.bulk_update import bulk_assign_roles

		failed = bulk_assign_roles(self.test_users, ["Accounts User"])
		self.assertEqual(failed, [])

		for email in self.test_users:
			user = frappe.get_doc("User", email)
			roles = [r.role for r in user.roles]
			self.assertIn("Accounts User", roles)
			self.assertIn("Desk User", roles)

	def test_bulk_assign_roles_failed_list(self):
		"""Invalid docname should appear in failed list not raise exception"""
		from frappe.desk.doctype.bulk_update.bulk_update import bulk_assign_roles

		failed = bulk_assign_roles(["nonexistent@example.com"], ["Accounts User"])
		self.assertIn("nonexistent@example.com", failed)

	def test_bulk_assign_roles_duplicate_skip(self):
		"""Assigning an already assigned role should not create duplicate rows"""
		from frappe.desk.doctype.bulk_update.bulk_update import bulk_assign_roles

		bulk_assign_roles([self.test_users[0]], ["Accounts User"])
		bulk_assign_roles([self.test_users[0]], ["Accounts User"])

		user = frappe.get_doc("User", self.test_users[0])
		blogger_count = sum(1 for r in user.roles if r.role == "Accounts User")
		self.assertEqual(blogger_count, 1)

	def test_bulk_assign_multiple_roles(self):
		"""Multiple roles can be assigned in a single call"""
		from frappe.desk.doctype.bulk_update.bulk_update import bulk_assign_roles

		failed = bulk_assign_roles([self.test_users[0]], ["Accounts User", "Sales User"])
		self.assertEqual(failed, [])

		user = frappe.get_doc("User", self.test_users[0])
		roles = [r.role for r in user.roles]
		self.assertIn("Accounts User", roles)
		self.assertIn("Sales User", roles)
