# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.app import _claims_raw_body, init_request
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request


class TestStreamingRequestPaths(IntegrationTestCase):
	"""The `streaming_request_paths` hook lets an app claim path prefixes whose
	request bodies it consumes itself: no max_content_length cap, no form_dict
	buffering, request.stream left intact."""

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def _init_request(self, path: str, data: bytes = b"", content_type: str = "application/octet-stream"):
		set_request(
			method="PUT",
			path=path,
			data=data,
			content_type=content_type,
			headers={"X-Frappe-Site-Name": frappe.local.site},
		)
		init_request(frappe.local.request)
		return frappe.local.request

	def test_claims_raw_body_matches_registered_prefixes_only(self):
		with self.patch_hooks({"streaming_request_paths": ["/dav/"]}):
			set_request(method="PUT", path="/dav/file.bin")
			self.assertTrue(_claims_raw_body(frappe.local.request))

			set_request(method="PUT", path="/davsomething")
			self.assertFalse(_claims_raw_body(frappe.local.request))

			set_request(method="PUT", path="/api/method/ping")
			self.assertFalse(_claims_raw_body(frappe.local.request))

	def test_claims_nothing_when_hook_absent(self):
		set_request(method="PUT", path="/dav/file.bin")
		self.assertFalse(_claims_raw_body(frappe.local.request))

	def test_claimed_path_skips_cap_and_form_dict(self):
		body = b"\x00\x01binary body" * 100
		with self.patch_hooks({"streaming_request_paths": ["/dav/"]}):
			request = self._init_request("/dav/file.bin?foo=bar", data=body)

		self.assertIsNone(request.max_content_length)
		self.assertEqual(frappe.local.form_dict, {})
		# body was not consumed by form parsing and streams intact
		self.assertEqual(request.stream.read(), body)
		# query args stay reachable outside form_dict
		self.assertEqual(request.args["foo"], "bar")

	def test_unclaimed_path_behaves_as_before(self):
		request = self._init_request(
			"/unclaimed", data=b'{"hello": "world"}', content_type="application/json"
		)

		self.assertIsNotNone(request.max_content_length)
		self.assertGreater(request.max_content_length, 0)
		self.assertEqual(frappe.local.form_dict.get("hello"), "world")
