# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.core.doctype.user.test_user import test_user
from frappe.desk.form.assign_to import add, get
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request


class TestAssign(IntegrationTestCase):
	def test_assign_respects_user_permissions_on_assignee(self):
		with test_user(roles=["Desk User"]) as actor, test_user(roles=["Desk User"]) as hidden:
			frappe.get_doc(
				doctype="User Permission", user=actor.name, allow="User", for_value=actor.name
			).insert()
			with self.set_user(actor.name):
				todo = frappe.get_doc(doctype="ToDo", description="assign scope").insert()
				args = {"doctype": "ToDo", "name": todo.name}

				set_request(method="POST", path="/api/method/frappe.desk.form.assign_to.add")
				self.addCleanup(setattr, frappe.local, "request", None)
				with self.assertRaises(frappe.LinkValidationError):
					add({**args, "assign_to": [hidden.name]})

				frappe.local.request = None
				add({**args, "assign_to": [hidden.name]})
				add({**args, "assign_to": [actor.name]})
				self.assertEqual(len(get(args)), 2)
