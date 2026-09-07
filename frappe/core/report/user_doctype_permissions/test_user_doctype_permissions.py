# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from unittest.mock import patch

from frappe.core.report.user_doctype_permissions.user_doctype_permissions import get_data
from frappe.tests import UnitTestCase


class TestUserDoctypePermissions(UnitTestCase):
	def test_ignores_permission_without_parent(self):
		user = "test@example.com"
		permissions = [
			{"parent": None, "permlevel": 0, "if_owner": 0, "role": "System Manager", "read": 1},
			{"parent": "ToDo", "permlevel": 0, "if_owner": 0, "role": "System Manager", "read": 1},
		]

		with (
			patch(
				"frappe.core.report.user_doctype_permissions.user_doctype_permissions.get_valid_perms",
				return_value=permissions,
			),
			patch(
				"frappe.core.report.user_doctype_permissions.user_doctype_permissions.get_perm_types",
				return_value=["read"],
			),
		):
			result = get_data({"user": user})

		self.assertEqual(result, [[user, "ToDo", 0, 1]])
