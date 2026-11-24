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
from frappe.tests import IntegrationTestCase
from frappe.utils import get_user_by_email


class TestAssign(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_test_doctype(TEST_DOCTYPE)

	def test_assign(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "test"}).insert()
		if not frappe.db.exists("User", {"email": "test@example.com"}):
			frappe.get_doc({"doctype": "User", "email": "test@example.com", "first_name": "Test"}).insert()

		self._test_basic_assign_on_document(todo)

	def _test_basic_assign_on_document(self, doc):
		user = get_user_by_email("test@example.com")
		added = assign(doc, user)

		self.assertTrue(user in [d.owner for d in added])

		frappe.desk.form.assign_to.remove(doc.doctype, doc.name, user)

		# assignment is cleared
		assignments = frappe.desk.form.assign_to.get(dict(doctype=doc.doctype, name=doc.name))
		self.assertEqual(len(assignments), 0)

	def test_assign_single(self):
		c = frappe.get_doc("Contact Us Settings")
		self._test_basic_assign_on_document(c)

	def test_assignment_count(self):
		frappe.db.delete("ToDo")

		if not (user1 := get_user_by_email("test_assign1@example.com")):
			user1 = (
				frappe.get_doc(
					{
						"doctype": "User",
						"email": "test_assign1@example.com",
						"first_name": "Test",
						"roles": [{"role": "System Manager"}],
					}
				)
				.insert()
				.name
			)

		if not (user2 := get_user_by_email("test_assign2@example.com")):
			user2 = (
				frappe.get_doc(
					{
						"doctype": "User",
						"email": "test_assign2@example.com",
						"first_name": "Test",
						"roles": [{"role": "System Manager"}],
					}
				)
				.insert()
				.name
			)

		note = _make_test_record()
		assign(note, user1)

		note = _make_test_record(public=1)
		assign(note, user2)

		note = _make_test_record(public=1)
		assign(note, user2)

		note = _make_test_record()
		assign(note, user2)

		data = {d.name: d.count for d in get_group_by_count(TEST_DOCTYPE, "[]", "assigned_to")}

		self.assertTrue(user1 in data)
		self.assertEqual(data[user1], 1)
		self.assertEqual(data[user2], 3)

		data = {d.name: d.count for d in get_group_by_count(TEST_DOCTYPE, '[{"public": 1}]', "assigned_to")}

		self.assertFalse(user1 in data)
		self.assertEqual(data[user2], 2)

		frappe.db.rollback()

	def test_assignment_removal(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "test"}).insert()
		if not frappe.db.exists("User", {"email": "test@example.com"}):
			frappe.get_doc({"doctype": "User", "email": "test@example.com", "first_name": "Test"}).insert()

		new_todo = assign(todo, get_user_by_email("test@example.com"))

		# remove assignment
		frappe.db.set_value("ToDo", new_todo[0].name, "allocated_to", "")

		self.assertFalse(get_assignments("ToDo", todo.name))

	def test_assign_filter_with_equals_operator(self):
		from frappe.model.qb_query import DatabaseQuery

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


def assign(doc, user):
	return frappe.desk.form.assign_to.add(
		{
			"assign_to": [user],
			"doctype": doc.doctype,
			"name": doc.name,
			"description": "test",
		}
	)
