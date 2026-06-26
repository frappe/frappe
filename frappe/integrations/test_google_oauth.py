# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.integrations.google_oauth import callback
from frappe.tests import IntegrationTestCase


class TestGoogleOAuth(IntegrationTestCase):
	def test_callback_accepts_native_state_dict(self):
		frappe.local.response = frappe._dict()
		# state as a native dict instead of a JSON string (frappe.parse_json passthrough);
		# an error short-circuits the domain dispatch and just redirects back
		callback(
			state={"redirect": "/app/todo", "failure_query_param": "failed=1"},
			error="access_denied",
		)
		self.assertEqual(frappe.local.response["type"], "redirect")
		self.assertEqual(frappe.local.response["location"], "/app/todo?failed=1")
