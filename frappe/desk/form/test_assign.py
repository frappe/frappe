# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.core.doctype.user.test_user import test_user
from frappe.desk.form.assign_to import add, get, remove_multiple
from frappe.tests import IntegrationTestCase


class TestAssign(IntegrationTestCase):
	def test_remove_multiple_accepts_native_list(self):
		frappe.set_user("Administrator")
		frappe.db.set_value("User", "Administrator", "bulk_actions", 1)
		frappe.clear_cache(doctype="User")

		todo1 = frappe.get_doc(doctype="ToDo", description="assign 1").insert()
		todo2 = frappe.get_doc(doctype="ToDo", description="assign 2").insert()
		for todo in (todo1, todo2):
			add({"doctype": "ToDo", "name": todo.name, "assign_to": ["Administrator"]})

		# names as a native list instead of a JSON string (frappe.parse_json passthrough)
		remove_multiple("ToDo", [todo1.name, todo2.name])

		self.assertEqual(get({"doctype": "ToDo", "name": todo1.name}), [])
		self.assertEqual(get({"doctype": "ToDo", "name": todo2.name}), [])

		todo1.delete()
		todo2.delete()

	def test_assign_respects_user_permissions_on_assignee(self):
		with test_user(roles=["Desk User"]) as actor, test_user(roles=["Desk User"]) as hidden:
			frappe.get_doc(
				doctype="User Permission", user=actor.name, allow="User", for_value=actor.name
			).insert()
			with self.set_user(actor.name):
				todo = frappe.get_doc(doctype="ToDo", description="assign scope").insert()
				args = {"doctype": "ToDo", "name": todo.name}

				with self.assertRaises(frappe.LinkValidationError):
					add({**args, "assign_to": [hidden.name]})

				add({**args, "assign_to": [actor.name]})
				self.assertEqual(len(get(args)), 1)
