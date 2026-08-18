# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.tests import IntegrationTestCase


class TestCustomDocPerm(IntegrationTestCase):
	def test_if_owner_cleared_for_high_permlevel(self):
		"""`if_owner` is only honoured at permlevel 0; it is cleared at higher levels."""
		perm = frappe.new_doc("Custom DocPerm")
		perm.update({"parent": "User", "role": "All", "permlevel": 1, "if_owner": 1, "read": 1})
		perm.validate()
		self.assertEqual(perm.if_owner, 0)

		perm = frappe.new_doc("Custom DocPerm")
		perm.update({"parent": "User", "role": "All", "permlevel": 0, "if_owner": 1, "read": 1})
		perm.validate()
		self.assertEqual(perm.if_owner, 1)
