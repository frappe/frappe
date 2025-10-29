# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.core.doctype.doctype.doctype import clear_permissions_cache
from frappe.model.db_query import DatabaseQuery
from frappe.permissions import add_permission, reset_perms
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = ["User", "Web Page"]


class TestToDo(IntegrationTestCase):
	def test_delete(self):
		todo = frappe.get_doc(doctype="ToDo", description="test todo", assigned_by="Administrator").insert()

		frappe.db.delete("Deleted Document")
		todo.delete()

		deleted = frappe.get_doc(
			"Deleted Document", dict(deleted_doctype=todo.doctype, deleted_name=todo.name)
		)
		self.assertEqual(todo.as_json(), deleted.data)

	def test_fetch(self):
		todo = frappe.get_doc(doctype="ToDo", description="test todo", assigned_by="Administrator").insert()
		self.assertEqual(
			todo.assigned_by_full_name, frappe.db.get_value("User", todo.assigned_by, "full_name")
		)

	def test_fetch_setup(self):
		frappe.db.delete("ToDo")

		todo_meta = frappe.get_meta("ToDo")
		todo_meta.get("fields", dict(fieldname="assigned_by_full_name"))[0].fetch_from = ""
		todo_meta.save()

		frappe.clear_cache(doctype="ToDo")

		todo = frappe.get_doc(doctype="ToDo", description="test todo", assigned_by="Administrator").insert()
		self.assertFalse(todo.assigned_by_full_name)

		todo_meta = frappe.get_meta("ToDo")
		todo_meta.get("fields", dict(fieldname="assigned_by_full_name"))[
			0
		].fetch_from = "assigned_by.full_name"
		todo_meta.save()

		todo.reload()
		todo.save()

		self.assertEqual(
			todo.assigned_by_full_name, frappe.db.get_value("User", todo.assigned_by, "full_name")
		)

	def test_todo_list_access(self):
		create_new_todo("Test1", "testperm@example.com")

		frappe.set_user("test4@example.com")
		create_new_todo("Test2", "test4@example.com")
		test_user_data = DatabaseQuery("ToDo").execute()

		frappe.set_user("testperm@example.com")
		system_manager_data = DatabaseQuery("ToDo").execute()

		self.assertNotEqual(test_user_data, system_manager_data)

		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_doc_read_access(self):
		# owner and assigned_by is testperm
		todo1 = create_new_todo("Test1", "testperm@example.com")
		test_user = frappe.get_doc("User", "test4@example.com")

		# owner is testperm, but assigned_by is test4
		todo2 = create_new_todo("Test2", "test4@example.com")

		frappe.set_user("test4@example.com")
		# owner and assigned_by is test4
		todo3 = create_new_todo("Test3", "test4@example.com")

		# user without any role to read or write todo document
		self.assertFalse(todo1.has_permission("read"))
		self.assertFalse(todo1.has_permission("write"))

		# user without any role but he/she is assigned_by of that todo document
		self.assertTrue(todo2.has_permission("read"))
		self.assertTrue(todo2.has_permission("write"))

		# user is the owner and assigned_by of the todo document
		self.assertTrue(todo3.has_permission("read"))
		self.assertTrue(todo3.has_permission("write"))

		frappe.set_user("Administrator")

		test_user.add_roles("Website Manager")
		add_permission("ToDo", "Website Manager")

		frappe.set_user("test4@example.com")

		# user with only read access to todo document, not an owner or assigned_by
		self.assertTrue(todo1.has_permission("read"))
		self.assertFalse(todo1.has_permission("write"))

		frappe.set_user("Administrator")
		test_user.remove_roles("Website Manager")
		reset_perms("ToDo")
		clear_permissions_cache("ToDo")
		frappe.db.rollback()

	def test_fetch_if_empty(self):
		frappe.db.delete("ToDo")

		# Allow user changes
		todo_meta = frappe.get_meta("ToDo")
		field = todo_meta.get("fields", dict(fieldname="assigned_by_full_name"))[0]
		field.fetch_from = "assigned_by.full_name"
		field.fetch_if_empty = 1
		todo_meta.save()

		frappe.clear_cache(doctype="ToDo")

		todo = frappe.get_doc(
			doctype="ToDo",
			description="test todo",
			assigned_by="Administrator",
			assigned_by_full_name="Admin",
		).insert()

		self.assertEqual(todo.assigned_by_full_name, "Admin")

		# Overwrite user changes
		todo.meta.get("fields", dict(fieldname="assigned_by_full_name"))[0].fetch_if_empty = 0
		todo.meta.save()

		todo.reload()
		todo.save()

		self.assertEqual(
			todo.assigned_by_full_name, frappe.db.get_value("User", todo.assigned_by, "full_name")
		)


def create_new_todo(description, assigned_by):
	todo = {"doctype": "ToDo", "description": description, "assigned_by": assigned_by}
	return frappe.get_doc(todo).insert()
