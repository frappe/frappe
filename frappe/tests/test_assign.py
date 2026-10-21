# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
import frappe.desk.form.assign_to
from frappe.automation.doctype.assignment_rule.test_assignment_rule import (
	TEST_DOCTYPE,
	_make_test_record,
	create_test_doctype,
)
from frappe.desk.form.load import get_assignments
from frappe.desk.listview import get_group_by_count
from frappe.tests.utils import FrappeTestCase


class TestAssign(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_test_doctype(TEST_DOCTYPE)

	def test_assign(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "test"}).insert()
		if not frappe.db.exists("User", "test@example.com"):
			frappe.get_doc({"doctype": "User", "email": "test@example.com", "first_name": "Test"}).insert()

		self._test_basic_assign_on_document(todo)

	def _test_basic_assign_on_document(self, doc):
		added = assign(doc, "test@example.com")

		self.assertTrue("test@example.com" in [d.owner for d in added])

		frappe.desk.form.assign_to.remove(doc.doctype, doc.name, "test@example.com")

		# assignment is cleared
		assignments = frappe.desk.form.assign_to.get(dict(doctype=doc.doctype, name=doc.name))
		self.assertEqual(len(assignments), 0)

	def test_assign_single(self):
		c = frappe.get_doc("Contact Us Settings")
		self._test_basic_assign_on_document(c)

	def test_assignment_count(self):
		frappe.db.delete("ToDo")

		if not frappe.db.exists("User", "test_assign1@example.com"):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": "test_assign1@example.com",
					"first_name": "Test",
					"roles": [{"role": "System Manager"}],
				}
			).insert()

		if not frappe.db.exists("User", "test_assign2@example.com"):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": "test_assign2@example.com",
					"first_name": "Test",
					"roles": [{"role": "System Manager"}],
				}
			).insert()

		note = _make_test_record()
		assign(note, "test_assign1@example.com")

		note = _make_test_record(public=1)
		assign(note, "test_assign2@example.com")

		note = _make_test_record(public=1)
		assign(note, "test_assign2@example.com")

		note = _make_test_record()
		assign(note, "test_assign2@example.com")

		data = {d.name: d.count for d in get_group_by_count(TEST_DOCTYPE, "[]", "assigned_to")}

		self.assertTrue("test_assign1@example.com" in data)
		self.assertEqual(data["test_assign1@example.com"], 1)
		self.assertEqual(data["test_assign2@example.com"], 3)

		data = {d.name: d.count for d in get_group_by_count(TEST_DOCTYPE, '[{"public": 1}]', "assigned_to")}

		self.assertFalse("test_assign1@example.com" in data)
		self.assertEqual(data["test_assign2@example.com"], 2)

		frappe.db.rollback()

	def test_assignment_removal(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "test"}).insert()
		if not frappe.db.exists("User", "test@example.com"):
			frappe.get_doc({"doctype": "User", "email": "test@example.com", "first_name": "Test"}).insert()

		new_todo = assign(todo, "test@example.com")

		# remove assignment
		frappe.db.set_value("ToDo", new_todo[0].name, "allocated_to", "")

		self.assertFalse(get_assignments("ToDo", todo.name))

<<<<<<< HEAD
=======
	def test_removing_other_users_assignment_requires_write(self):
		from frappe.permissions import add_permission, update_permission_property

		for role in ("Assign Reader", "Assign Writer"):
			if not frappe.db.exists("Role", role):
				frappe.get_doc({"doctype": "Role", "role_name": role}).insert()
			add_permission("Note", role, 0)
		update_permission_property("Note", "Assign Writer", 0, "write", 1)

		users = {}
		for key, role in (
			("assignee", "Assign Reader"),
			("reader", "Assign Reader"),
			("writer", "Assign Writer"),
		):
			email = f"assign_{key}@example.com"
			if not frappe.db.exists("User", email):
				frappe.get_doc(
					{
						"doctype": "User",
						"email": email,
						"first_name": key,
						"roles": [{"role": role}],
					}
				).insert()
			users[key] = email

		note = frappe.get_doc({"doctype": "Note", "title": "assign test", "public": 1}).insert()
		assign(note, users["assignee"])

		def remove_as(user):
			frappe.set_user(user)
			try:
				return frappe.desk.form.assign_to.remove(note.doctype, note.name, users["assignee"])
			finally:
				frappe.set_user("Administrator")

		with self.assertRaises(frappe.PermissionError):
			remove_as(users["reader"])
		self.assertTrue(get_assignments("Note", note.name))

		remove_as(users["writer"])
		self.assertFalse(get_assignments("Note", note.name))

		assign(note, users["assignee"])
		remove_as(users["assignee"])
		self.assertFalse(get_assignments("Note", note.name))

	def test_assign_filter_with_equals_operator(self):
		from frappe.model.db_query import DatabaseQuery

		todo = frappe.get_doc({"doctype": "ToDo", "description": "assign filter test"}).insert()
		frappe.db.set_value("ToDo", todo.name, "_assign", frappe.as_json(["test@example.com"]))

		# _assign stores a JSON array of users, so `=` / `!=` must match like `like` / `not like`
		for run_filter in (
			lambda op: frappe.get_all("ToDo", filters=[["_assign", op, "test@example.com"]], pluck="name"),
			lambda op: DatabaseQuery("ToDo").execute(
				filters=[["_assign", op, "test@example.com"]], pluck="name"
			),
		):
			self.assertIn(todo.name, run_filter("="))
			self.assertNotIn(todo.name, run_filter("!="))

>>>>>>> a961f01 (fix(assign_to): require write permission to remove another user's assignment)

def assign(doc, user):
	return frappe.desk.form.assign_to.add(
		{
			"assign_to": [user],
			"doctype": doc.doctype,
			"name": doc.name,
			"description": "test",
		}
	)
