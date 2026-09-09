# Copyright (c) 2024, Frappe Technologies Pvt Ltd and Contributors
# See license.txt

# import frappe
from frappe.tests.utils import FrappeTestCase

from studio.export import remove_empty_values


class TestStudioPage(FrappeTestCase):
	def test_remove_empty_values(self):
		test_dict = {
			"keep_this": "value",
			"keep_false": False,
			"keep_zero": 0,
			"remove_this_null": None,
			"remove_this_empty_list": [],
			"remove_this_empty_dict": {},
			"nested_config": {"empty_value": "", "empty_dict": {}},
			"blocks": [
				{
					"componentName": "Button",
					"remove_empty_string": "",
					"remove_empty_list": [],
					"remove_empty_dict": {},
					"componentProps": {"empty_value": "", "false_value": False},
					"componentSlots": {},
					"children": [
						{"componentName": "TextBlock", "remove_empty_string": ""},
					],
				}
			],
		}
		remove_empty_values(test_dict)
		self.assertEqual(
			test_dict,
			{
				"keep_this": "value",
				"keep_false": False,
				"keep_zero": 0,
				"nested_config": {"empty_value": "", "empty_dict": {}},
				"blocks": [
					{
						"componentName": "Button",
						"componentProps": {"empty_value": "", "false_value": False},
						"componentSlots": {},
						"children": [{"componentName": "TextBlock"}],
					}
				],
			},
		)
