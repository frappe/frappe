# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
from unittest.mock import patch

import frappe
from frappe.integrations import google_oauth
from frappe.integrations.google_oauth import callback, create_google_oauth_state
from frappe.tests.utils import FrappeTestCase

_dispatched_calls = []


def _fake_domain_callback(code=None, **kwargs):
	"""Stand-in for a real domain callback (e.g. authorize_access) so tests don't hit Google."""
	_dispatched_calls.append({"code": code, **kwargs})


class TestGoogleOAuth(FrappeTestCase):
	def setUp(self):
		self._original_response = frappe.local.response
		frappe.local.response = frappe._dict()

	def tearDown(self):
		frappe.local.response = self._original_response

	def test_callback_uses_server_side_state(self):
		state_token = create_google_oauth_state({"redirect": "/app/todo", "failure_query_param": "failed=1"})
		# an error short-circuits the domain dispatch and just redirects back
		callback(state=state_token, error="access_denied")
		self.assertEqual(frappe.local.response["type"], "redirect")
		self.assertEqual(frappe.local.response["location"], "/app/todo?failed=1")

	def test_callback_success_dispatches_domain_and_redirects(self):
		"""The normal, non-error flow: domain callback is invoked and the success redirect fires."""
		_dispatched_calls.clear()
		state_token = create_google_oauth_state(
			{
				"domain": "test-domain",
				"redirect": "/app/todo",
				"success_query_param": "connected=1",
				"doc_name": "abc",
			}
		)
		fake_path = "frappe.integrations.test_google_oauth._fake_domain_callback"
		with patch.dict(google_oauth._DOMAIN_CALLBACK_METHODS, {"test-domain": fake_path}):
			callback(state=state_token, code="real-auth-code")

		self.assertEqual(_dispatched_calls, [{"code": "real-auth-code", "doc_name": "abc"}])
		self.assertEqual(frappe.local.response["type"], "redirect")
		self.assertEqual(frappe.local.response["location"], "/app/todo?connected=1")

	def test_callback_dispatches_via_state_callback_method(self):
		_dispatched_calls.clear()
		frappe.local.response = frappe._dict()
		state_token = create_google_oauth_state(
			{
				"domain": "drive",
				"callback_method": "frappe.integrations.test_google_oauth._fake_domain_callback",
				"redirect": "/app/todo",
				"success_query_param": "connected=1",
			}
		)
		# "drive" is deliberately absent from _DOMAIN_CALLBACK_METHODS here
		callback(state=state_token, code="real-auth-code")

		self.assertEqual(_dispatched_calls, [{"code": "real-auth-code"}])
		self.assertEqual(frappe.local.response["location"], "/app/todo?connected=1")

	def test_callback_rejects_unknown_state(self):
		callback(state="not-a-real-token", error="access_denied")
		self.assertEqual(frappe.local.response["type"], "page")
		self.assertEqual(frappe.local.response["http_status_code"], 417)

	def test_callback_rejects_client_supplied_state(self):
		"""A caller can no longer smuggle a redirect target in via the `state` param itself."""
		forged = json.dumps({"redirect": "https://evil.example.com", "domain": "contacts"})
		callback(state=forged, error="access_denied")
		self.assertEqual(frappe.local.response["type"], "page")
		self.assertNotIn("evil.example.com", frappe.local.response.get("location", ""))
