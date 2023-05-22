# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from frappe.tests.utils import FrappeTestCase
from frappe.utils.logger import sanitized_dict

# test_records = frappe.get_test_records('Error Snapshot')


class TestErrorSnapshot(FrappeTestCase):
	def test_form_dict_sanitization(self):
		self.assertNotEqual(sanitized_dict({"pwd": "SECRET", "usr": "WHAT"}).get("pwd"), "SECRET")
