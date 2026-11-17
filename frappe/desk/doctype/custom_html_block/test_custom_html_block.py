# Copyright (c) 2023, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.core.doctype.user.test_user import test_user
from frappe.desk.doctype.custom_html_block.custom_html_block import get_custom_blocks_for_user
from frappe.tests import IntegrationTestCase


class TestCustomHTMLBlock(IntegrationTestCase):
	def test_query_allows_null_filters(self):
		result = get_custom_blocks_for_user("Custom HTML Block", "", "name", 0, 20, None)
		self.assertIsInstance(result, list | tuple)

	def test_query_requires_read_permission(self):
		with test_user(roles=[], user_type="Website User") as user, self.set_user(user.name):
			with self.assertRaises(frappe.PermissionError):
				get_custom_blocks_for_user("Custom HTML Block", "", "name", 0, 20, None)
