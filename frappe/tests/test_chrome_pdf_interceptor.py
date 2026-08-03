# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import os
import tempfile
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
	return page


def _make_session(captured):
	"""Mock CDP session that captures the Fetch.requestPaused callback and records send() calls."""
	session = MagicMock()

	def fake_start_listener(event_name, callback, *args):
		if event_name == "Fetch.requestPaused":
			captured[0] = callback

	session.start_listener.side_effect = fake_start_listener
	return session


def _fire_request(callback, request_id, url):
	"""Simulate Chrome firing a Fetch.requestPaused CDP event."""
	callback(
		future=MagicMock(),
		response={
			"params": {
				"requestId": request_id,
				"request": {"url": url},
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
			_fire_request(callback, "req-1", HOST)

		self.session.send.assert_any_call("Fetch.continueRequest", {"requestId": "req-1"}, return_future=True)
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
		Requests for URLs outside the site host are passed through to the network.
		"""
		callback = self._register()

		with patch("frappe.utils.chromium.page.get_host_url", return_value=HOST):
			_fire_request(callback, "req-4", "https://cdn.example.com/some.js")

		sent = self._sent_methods()
		self.assertIn("Fetch.continueRequest", sent)
		self.assertNotIn("Fetch.fulfillRequest", sent)
		self.assertNotIn("Fetch.failRequest", sent)
