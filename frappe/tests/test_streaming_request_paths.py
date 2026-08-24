# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.app import _claims_raw_body, init_request
from frappe.auth import validate_oauth
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request

# A synthetic prefix used for init_request-level tests. It must be a prefix that no
# installed app actually claims (via a `before_request`/streaming hook), so these tests
# stay hermetic regardless of which apps are present on the test site.
PREFIX = "/streamtest/"


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
		with self.patch_hooks({"streaming_request_paths": [PREFIX]}):
			set_request(method="PUT", path=f"{PREFIX}file.bin")
			self.assertTrue(_claims_raw_body(frappe.local.request))

			set_request(method="PUT", path="/streamtestsomething")
			self.assertFalse(_claims_raw_body(frappe.local.request))

			set_request(method="PUT", path="/api/method/ping")
			self.assertFalse(_claims_raw_body(frappe.local.request))

	def test_claims_nothing_when_hook_empty(self):
		with self.patch_hooks({"streaming_request_paths": []}):
			set_request(method="PUT", path=f"{PREFIX}file.bin")
			self.assertFalse(_claims_raw_body(frappe.local.request))

	def test_match_enforces_path_segment_boundary(self):
		# a prefix without a trailing slash must not leak onto sibling routes
		with self.patch_hooks({"streaming_request_paths": ["/streamtest"]}):
			for path, claimed in (
				("/streamtest", True),
				("/streamtest/file.bin", True),
				("/streamtestsomething", False),
			):
				set_request(method="PUT", path=path)
				self.assertEqual(_claims_raw_body(frappe.local.request), claimed, path)

	def test_unsafe_prefixes_are_ignored(self):
		# empty / "/" / non-string prefixes must not disable body handling site-wide
		for prefix in ("", "/", 123):
			with self.patch_hooks({"streaming_request_paths": [prefix]}):
				set_request(method="PUT", path="/streamtest/x")
				self.assertFalse(_claims_raw_body(frappe.local.request), repr(prefix))

	def test_reserved_core_prefixes_are_never_claimed(self):
		# even if an app registers a framework-owned prefix, core routes must not be claimed
		for prefix, path in (
			("/api/", "/api/method/frappe.ping"),
			("/app", "/app/todo"),
			("/backups", "/backups/site.sql.gz"),
			("/private/", "/private/files/secret.pdf"),
		):
			with self.patch_hooks({"streaming_request_paths": [prefix]}):
				set_request(method="PUT", path=path)
				self.assertFalse(_claims_raw_body(frappe.local.request), f"{prefix} -> {path}")

	def test_claimed_path_skips_cap_and_form_dict(self):
		body = b"\x00\x01binary body" * 100
		with self.patch_hooks({"streaming_request_paths": [PREFIX]}):
			request = self._init_request(f"{PREFIX}file.bin?foo=bar", data=body)

		self.assertIsNone(request.max_content_length)
		self.assertEqual(frappe.local.form_dict, {})
		# body was not consumed by form parsing and streams intact
		self.assertEqual(request.stream.read(), body)
		# query args stay reachable outside form_dict
		self.assertEqual(request.args["foo"], "bar")

	def test_claimed_path_sets_environ_flag(self):
		with self.patch_hooks({"streaming_request_paths": [PREFIX]}):
			request = self._init_request(f"{PREFIX}file.bin", data=b"x")
		# the flag tells pre-handler auth (validate_oauth) not to read the raw body
		self.assertTrue(request.environ.get("frappe.claims_raw_body"))

	def test_oauth_bearer_does_not_consume_claimed_stream(self):
		"""A pre-auth bearer request on a claimed path must not read/buffer the body:
		an invalid token must return before get_data(), leaving request.stream intact
		(guards the unbounded-read DoS and the stream-truncation regression)."""
		body = b"streamed-put-body" * 200
		with self.patch_hooks({"streaming_request_paths": [PREFIX]}):
			request = self._init_request(f"{PREFIX}file.bin", data=body)
			validate_oauth(["Bearer", "an-invalid-token"])

		self.assertEqual(request.stream.read(), body)

	def test_unclaimed_path_behaves_as_before(self):
		with self.patch_hooks({"streaming_request_paths": [PREFIX]}):
			request = self._init_request(
				"/unclaimed", data=b'{"hello": "world"}', content_type="application/json"
			)

		self.assertIsNotNone(request.max_content_length)
		self.assertGreater(request.max_content_length, 0)
		self.assertEqual(frappe.local.form_dict.get("hello"), "world")
