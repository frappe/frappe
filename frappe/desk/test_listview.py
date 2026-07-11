# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.listview import get_group_by_count
from frappe.tests import IntegrationTestCase


class TestListView(IntegrationTestCase):
	def test_group_by_count_accepts_filters_as_list(self):
		# the client sends current_filters as a list, type validation must not reject it
		result = get_group_by_count("User", [], "enabled")
		self.assertIsInstance(result, list)

	def test_group_by_count_assigned_to_accepts_filters_as_list(self):
		result = get_group_by_count("User", [], "assigned_to")
		self.assertIsInstance(result, list)
