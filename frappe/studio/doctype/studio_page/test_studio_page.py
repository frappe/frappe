# Copyright (c) 2024, Frappe Technologies Pvt Ltd and Contributors
# See license.txt

# import frappe
from frappe.tests.utils import FrappeTestCase
from studio.export import remove_null_fields


class TestStudioPage(FrappeTestCase):
	def test_remove_null_fields(self):
		test_dict = {
			"keep_this": "value",
			"remove_this_null": None,
			"remove_this_empty_list": [],
			"remove_this_empty_dict": {
				"some_dict":{
					"some_more_dict":{

					}
				}
			},
			"nested_dict": {
				"keep_nested": 123,
				"remove_nested_null": None,
				"empty_nested_dict": {}
			},
			"nested_list": [
				{"keep_list_dict": "", "remove_list_null": None},
				{}
			],
			"new_nested_list":[
				{"new_nested_list":[
					{"new_nested_list_again":[]}

				],
				}
			]
		}
		remove_null_fields(test_dict)
		print(test_dict)
		self.assertEqual(test_dict, {
			"keep_this": "value",
			"nested_dict": {
				"keep_nested": 123
			}
		})
