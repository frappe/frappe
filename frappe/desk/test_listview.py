# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from frappe.desk.listview import get_group_by_count
from frappe.tests import IntegrationTestCase


class TestListView(IntegrationTestCase):
	def test_group_by_count_accepts_filters_as_list(self):
		# the client sends current_filters as a list of [doctype, field, operator, value]
		# arrays; type validation must accept it, not just a JSON string
		filters = [["User", "enabled", "=", 1]]
		result = get_group_by_count("User", filters, "enabled")
		self.assertIsInstance(result, list)

	def test_group_by_count_assigned_to_accepts_filters_as_list(self):
		filters = [["User", "enabled", "=", 1]]
		result = get_group_by_count("User", filters, "assigned_to")
		self.assertIsInstance(result, list)
