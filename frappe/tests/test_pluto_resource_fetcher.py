# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import importlib.util
import io
import unittest
from unittest.mock import MagicMock, patch

from requests import Request, Response
from urllib3 import HTTPResponse

import frappe
from frappe.tests import UnitTestCase

HAS_PLUTOPRINT = importlib.util.find_spec("plutoprint") is not None

PUBLIC_IMAGE = "https://8.8.8.8/logo.png"


def _response(status_code, **headers):
	response = Response()
	response.status_code = status_code
	response.url = PUBLIC_IMAGE
	response.request = Request("GET", PUBLIC_IMAGE).prepare()
	response.headers.update(headers)
	response.raw = HTTPResponse(body=io.BytesIO(b"image"), preload_content=False)
	return response


@unittest.skipUnless(HAS_PLUTOPRINT, "plutoprint is not installed")
class TestPlutoResourceFetcher(UnitTestCase):
	def setUp(self):
		from frappe.utils.pdf_generator.pluto import local_resource_fetcher

		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		self.fetcher = local_resource_fetcher()

	def test_request_address_validation(self):
		import plutoprint

		with self.assertRaises(plutoprint.Error):
			self.fetcher.fetch("http://127.0.0.1/logo.png")

	def test_redirect_address_validation(self):
		import plutoprint

		redirect = _response(302, Location="http://127.0.0.1/logo.png")
		with patch("requests.adapters.HTTPAdapter.send", return_value=redirect) as send:
			with self.assertRaises(plutoprint.Error):
				self.fetcher.fetch(PUBLIC_IMAGE)
		send.assert_called_once()

	def test_public_image_is_fetched(self):
		image = _response(200, **{"Content-Type": "image/png"})
		with patch("requests.adapters.HTTPAdapter.send", return_value=image):
			self.assertEqual(self.fetcher.fetch(PUBLIC_IMAGE).get_mime_type(), "image/png")

	def test_failed_url_is_fetched_once(self):
		import plutoprint

		with patch("requests.adapters.HTTPAdapter.send", return_value=_response(404)) as send:
			for _attempt in range(2):
				with self.assertRaises(plutoprint.Error):
					self.fetcher.fetch_url(PUBLIC_IMAGE)
		send.assert_called_once()

	def test_image_past_the_deadline_is_abandoned(self):
		import plutoprint

		image = _response(200, **{"Content-Type": "image/png"})
		with (
			patch("requests.adapters.HTTPAdapter.send", return_value=image),
			patch("frappe.utils.pdf_generator.page.EXTERNAL_FETCH_SECONDS", -1),
			self.assertRaises(plutoprint.Error),
		):
			self.fetcher.fetch(PUBLIC_IMAGE)

	def test_data_uri_is_not_blocked(self):
		resource = MagicMock()
		resource.get_mime_type.return_value = "image/png"

		with patch("plutoprint.default_resource_fetcher") as default_fetcher:
			default_fetcher.fetch_url.return_value = resource
			self.assertIs(self.fetcher.fetch("data:image/png;base64,iVBORw0KGgo="), resource)
