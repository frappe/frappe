# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import os
import tempfile
from concurrent.futures import Future
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import UnitTestCase
from frappe.utils.chromium.page import Page


def _make_page(session):
	"""Create a Page instance without triggering __init__ (which requires a live CDP session)."""
	page = object.__new__(Page)
	page.session = session
	page.session_id = "test_session"
	page.target_id = "test_target"
	page.frame_id = "test_frame"
	page.block_external_requests = False
	return page


def _run_in_executor(executor, func, *args):
	future = Future()
	future.set_result(func(*args))
	return future


def _make_session(captured):
	"""Mock CDP session that captures the Fetch.requestPaused callback and records send() calls."""
	session = MagicMock()
	session.loop.run_in_executor.side_effect = _run_in_executor

	def fake_start_listener(event_name, callback, *args):
		if event_name == "Fetch.requestPaused":
			captured[0] = callback

	session.start_listener.side_effect = fake_start_listener
	return session


def _fire_request(callback, request_id, url, **params):
	"""Simulate Chrome firing a Fetch.requestPaused CDP event."""
	callback(
		future=MagicMock(),
		response={
			"params": {
				"requestId": request_id,
				"request": {"url": url, "method": "GET"},
				**params,
			}
		},
	)


HOST = "https://example.frappe.test/"


class TestChromePDFLocalResourceInterceptor(UnitTestCase):
	"""Tests for the path-safety logic in Page.intercept_request_for_local_resources."""

	def setUp(self):
		self.captured = [None]
		self.session = _make_session(self.captured)
		self.page = _make_page(self.session)

	def _register(self):
		with patch("frappe.utils.chromium.page.get_host_url", return_value=HOST):
			self.page.intercept_request_for_local_resources()
		return self.captured[0]

	def _sent_methods(self):
		return [c.args[0] for c in self.session.send.call_args_list]

	def test_root_url_sends_continue_not_read(self):
		"""
		Chrome requests the site root URL during page setup (empty path after host strip).
		The interceptor must send continueRequest — not attempt to read the public root
		directory as a file.
		"""
		callback = self._register()

		with (
			patch("frappe.utils.chromium.page.get_host_url", return_value=HOST),
			patch("frappe.read_file") as mock_read,
		):
			_fire_request(callback, "req-1", HOST, resourceType="Document", frameId="test_frame")

		self.session.send.assert_any_call(
			"Fetch.continueRequest", {"requestId": "req-1"}, "test_session", True
		)
		mock_read.assert_not_called()

	def test_path_traversal_sends_fail(self):
		"""
		A path that resolves outside the site public root must be denied with failRequest.
		"""
		callback = self._register()

		with patch("frappe.utils.chromium.page.get_host_url", return_value=HOST):
			_fire_request(callback, "req-2", HOST + "../../etc/passwd")

		sent = self._sent_methods()
		self.assertIn("Fetch.failRequest", sent)
		self.assertNotIn("Fetch.fulfillRequest", sent)

	def test_existing_public_file_sends_fulfill(self):
		"""
		A real file under the site public root must be served with fulfillRequest.
		"""
		site_public_root = os.path.realpath(frappe.utils.get_site_path("public"))
		os.makedirs(site_public_root, exist_ok=True)

		fd, real_file = tempfile.mkstemp(dir=site_public_root, suffix=".txt")
		# the interceptor only fulfills when read_file returns a body, so the file can't be empty
		with os.fdopen(fd, "w") as f:
			f.write("test")
		self.addCleanup(os.remove, real_file)

		rel_path = os.path.relpath(real_file, site_public_root)
		callback = self._register()

		with patch("frappe.utils.chromium.page.get_host_url", return_value=HOST):
			_fire_request(callback, "req-3", HOST + rel_path)

		self.assertIn("Fetch.fulfillRequest", self._sent_methods())

	def test_unknown_origin_url_sends_continue(self):
		"""
		With internal URLs allowed in the common site config, requests for URLs outside
		the site host are passed through to the network.
		"""
		callback = self._register()

		with (
			patch("frappe.utils.chromium.page.get_host_url", return_value=HOST),
			patch("frappe.utils.chromium.page.allows_internal_print_urls", return_value=True),
		):
			_fire_request(callback, "req-4", "https://cdn.example.com/some.js")

		sent = self._sent_methods()
		self.assertIn("Fetch.continueRequest", sent)
		self.assertNotIn("Fetch.fulfillRequest", sent)
		self.assertNotIn("Fetch.failRequest", sent)

	def test_external_url_is_fulfilled_from_guarded_read(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		callback = self._register()

		with (
			patch("frappe.utils.chromium.page.get_host_url", return_value=HOST),
			patch(
				"frappe.utils.chromium.page.read_external_resource",
				return_value=(b"image", {"Content-Type": "image/png"}, 200),
			),
		):
			_fire_request(callback, "req-8", "https://cdn.example.com/logo.png")

		sent = self._sent_methods()
		self.assertIn("Fetch.fulfillRequest", sent)
		self.assertNotIn("Fetch.continueRequest", sent)

	def test_request_address_validation_sends_fail(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		callback = self._register()

		with patch("frappe.utils.chromium.page.get_host_url", return_value=HOST):
			_fire_request(callback, "req-6", "http://127.0.0.1/some.js")

		sent = self._sent_methods()
		self.assertIn("Fetch.failRequest", sent)
		self.assertNotIn("Fetch.continueRequest", sent)
		self.assertNotIn("Fetch.fulfillRequest", sent)

	def test_host_that_cannot_be_encoded_sends_fail(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		callback = self._register()

		with patch("frappe.utils.chromium.page.get_host_url", return_value=HOST):
			_fire_request(callback, "req-7", f"http://{'a' * 64}.example.com/logo.png")

		self.assertIn("Fetch.failRequest", self._sent_methods())

	def test_unknown_origin_url_sends_fail_when_external_requests_are_blocked(self):
		self.page.block_external_requests = True
		callback = self._register()

		with patch("frappe.utils.chromium.page.get_host_url", return_value=HOST):
			_fire_request(callback, "req-5", "http://169.254.169.254/latest/meta-data/")

		sent = self._sent_methods()
		self.assertIn("Fetch.failRequest", sent)
		self.assertNotIn("Fetch.continueRequest", sent)
