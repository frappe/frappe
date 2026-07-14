# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from frappe.desk.form.load import get_user_info_for_viewers
from frappe.tests import IntegrationTestCase


class TestLoad(IntegrationTestCase):
	def test_get_user_info_for_viewers_accepts_native_list(self):
		# users as a native list instead of a JSON string (frappe.parse_json passthrough)
		info = get_user_info_for_viewers(["Administrator"])
		self.assertIn("Administrator", info)
