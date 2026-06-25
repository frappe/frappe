# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
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
