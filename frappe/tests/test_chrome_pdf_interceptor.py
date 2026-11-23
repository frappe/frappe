# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import contextlib
import os
<<<<<<< HEAD
<<<<<<< HEAD
=======
=======
import socket
>>>>>>> 6ce1991 (test(print): external pdf resources end at their time limit)
import tempfile
import threading
import time
from concurrent.futures import Future
>>>>>>> 9026635 (test(print): pdf resources load through the safe request session)
from unittest.mock import MagicMock, patch

import frappe
<<<<<<< HEAD
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils.pdf_generator.page import Page
=======
from frappe.tests import UnitTestCase
from frappe.utils.chromium.page import Page, read_external_resource
>>>>>>> 6ce1991 (test(print): external pdf resources end at their time limit)


def _make_page(session):
	"""Create a Page instance without triggering __init__ (which requires a live CDP session)."""
	page = object.__new__(Page)
	page.session = session
	page.session_id = "test_session"
	page.target_id = "test_target"
	page.frame_id = "test_frame"
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


<<<<<<< HEAD
class TestPdfStreamHandle(UnitTestCase):
	def _page_with_pdf_futures(self, response):
		import asyncio

		loop = asyncio.new_event_loop()
		self.addCleanup(loop.close)
		response_future = loop.create_future()
		if response is not None:
			response_future.set_result(response)
		send_task = loop.create_future()
		send_task.set_result(response_future)
		page = _make_page(MagicMock())
		page.wait_for_pdf = send_task
		return page

	def test_returns_the_stream_once_the_response_arrived(self):
		page = self._page_with_pdf_futures({"result": {"stream": "handle-1"}})
		self.assertEqual(page.get_pdf_stream_id(), "handle-1")
		page.session.wait_for_event.assert_any_call(page.wait_for_pdf.result(), timeout=30)

	def test_raises_instead_of_reading_a_pending_response(self):
		page = self._page_with_pdf_futures(None)
		with self.assertRaises(RuntimeError):
			page.get_pdf_stream_id()


def _fire_request(callback, request_id, url):
=======
def _fire_request(callback, request_id, url, **params):
>>>>>>> 9026635 (test(print): pdf resources load through the safe request session)
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
		with patch("frappe.utils.pdf_generator.page.get_host_url", return_value=HOST):
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
			patch("frappe.utils.pdf_generator.page.get_host_url", return_value=HOST),
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

		with patch("frappe.utils.pdf_generator.page.get_host_url", return_value=HOST):
			_fire_request(callback, "req-2", HOST + "../../etc/passwd")

		sent = self._sent_methods()
		self.assertIn("Fetch.failRequest", sent)
		self.assertNotIn("Fetch.fulfillRequest", sent)

	def test_existing_public_file_sends_fulfill(self):
		"""
		A real file under the site public root must be served with fulfillRequest.

		Note: this test touches real disk via os.walk; it is skipped when
		site_public_root contains no files (e.g. a bare CI environment).
		"""
		site_public_root = os.path.realpath(frappe.utils.get_site_path("public"))
		real_file = None
		for root, _dirs, files in os.walk(site_public_root):
			for fname in files:
				candidate = os.path.join(root, fname)
				if os.path.isfile(candidate):
					real_file = candidate
					break
			if real_file:
				break

		if real_file is None:
			self.skipTest("No files found under site_public_root")

		rel_path = os.path.relpath(real_file, site_public_root)
		callback = self._register()

		with patch("frappe.utils.pdf_generator.page.get_host_url", return_value=HOST):
			_fire_request(callback, "req-3", HOST + rel_path)

		self.assertIn("Fetch.fulfillRequest", self._sent_methods())

	def test_unknown_origin_url_sends_continue(self):
		"""
		With internal URLs allowed in the common site config, requests for URLs outside
		the site host are passed through to the network.
		"""
		callback = self._register()

<<<<<<< HEAD
		with patch("frappe.utils.pdf_generator.page.get_host_url", return_value=HOST):
=======
		with (
			patch("frappe.utils.chromium.page.get_host_url", return_value=HOST),
			patch("frappe.utils.chromium.page.allows_internal_print_urls", return_value=True),
		):
>>>>>>> 9026635 (test(print): pdf resources load through the safe request session)
			_fire_request(callback, "req-4", "https://cdn.example.com/some.js")

		sent = self._sent_methods()
		self.assertIn("Fetch.continueRequest", sent)
		self.assertNotIn("Fetch.fulfillRequest", sent)
		self.assertNotIn("Fetch.failRequest", sent)

<<<<<<< HEAD
=======
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

	def test_external_read_ends_at_its_time_limit(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		server = socket.create_server(("127.0.0.1", 0))
		self.addCleanup(server.close)

		def respond():
			connection, _address = server.accept()
			with connection, contextlib.suppress(OSError):
				connection.recv(65536)
				connection.sendall(b"HTTP/1.1 200 OK\r\nX-Item: ")
				for _byte in range(60):
					connection.sendall(b"a")
					time.sleep(0.05)

		threading.Thread(target=respond, daemon=True).start()
		started = time.monotonic()
		with (
			patch("frappe.utils.safe_exec.validate_request_url"),
			patch("frappe.utils.safe_exec.validate_request_address"),
			patch("frappe.utils.chromium.page.EXTERNAL_FETCH_SECONDS", 0.3),
		):
			resource = read_external_resource(f"http://127.0.0.1:{server.getsockname()[1]}/logo.png", 1024)

		self.assertIsNone(resource)
		self.assertLess(time.monotonic() - started, 2)

	def test_unknown_origin_url_sends_fail_when_external_requests_are_blocked(self):
		self.page.block_external_requests = True
		callback = self._register()
>>>>>>> 9026635 (test(print): pdf resources load through the safe request session)

class TestChromePDFElementHeight(UnitTestCase):
	def setUp(self):
		self.session = MagicMock()
		self.page = _make_page(self.session)
		self.page.is_print_designer = False

	def test_measures_wrapper_with_ceil(self):
		with patch.object(Page, "evaluate", return_value={"result": {"value": 114}}) as evaluate:
			self.assertEqual(self.page.get_element_height(), 114)

		js = evaluate.call_args.args[0]
		self.assertIn("querySelector('.wrapper')", js)
		self.assertIn("getBoundingClientRect().height", js)
		self.assertIn("Math.ceil", js)
		self.assertNotIn("Math.round", js)

	def test_falls_back_to_box_model(self):
		responses = {
			"DOM.getDocument": ({"root": {"nodeId": 1}}, None),
			"DOM.querySelector": ({"nodeId": 2}, None),
			"DOM.getBoxModel": ({"model": {"height": 113}}, None),
		}
		self.session.send.side_effect = lambda method, *a: responses.get(method, (None, None))

		with patch.object(Page, "evaluate", side_effect=RuntimeError("boom")):
			self.assertEqual(self.page.get_element_height(), 113)

		self.assertIn("DOM.disable", [c.args[0] for c in self.session.send.call_args_list])


class TestChromePDFPrivateFiles(IntegrationTestCase):
	def setUp(self):
		self.captured = [None]
		self.session = _make_session(self.captured)
		self.page = _make_page(self.session)
		self.file = frappe.get_doc(
			doctype="File",
			file_name=f"{frappe.generate_hash(length=8)}.txt",
			content="private",
			is_private=1,
		).insert()
		self.addCleanup(frappe.delete_doc, "File", self.file.name, force=True)
		with patch("frappe.utils.pdf_generator.page.get_host_url", return_value=HOST):
			self.page.intercept_request_for_local_resources()
		self.callback = self.captured[0]

	def _fire(self, request_id, url):
		with patch("frappe.utils.pdf_generator.page.get_host_url", return_value=HOST):
			_fire_request(self.callback, request_id, url)
		return [c.args[0] for c in self.session.send.call_args_list]

	def _url(self, query=""):
		return f"{HOST}{self.file.file_url.lstrip('/')}{query}"

	def test_private_file_with_fid_is_served(self):
		self.assertIn("Fetch.fulfillRequest", self._fire("req-1", self._url(f"?fid={self.file.name}")))

	def test_private_file_is_denied_to_guest(self):
		frappe.set_user("Guest")
		self.addCleanup(frappe.set_user, "Administrator")
		sent = self._fire("req-2", self._url(f"?fid={self.file.name}"))
		self.assertIn("Fetch.failRequest", sent)
		self.assertNotIn("Fetch.fulfillRequest", sent)

	def test_private_file_traversal_is_denied(self):
		sent = self._fire("req-3", HOST + "private/files/../../site_config.json")
		self.assertIn("Fetch.failRequest", sent)
		self.assertNotIn("Fetch.fulfillRequest", sent)
