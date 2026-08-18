# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import unittest
from io import BytesIO

from PIL import Image

import frappe
from frappe.tests import IntegrationTestCase


def is_chromium_available() -> bool:
	"""True only if Chromium is already on disk.

	Avoids triggering a ~150MB download during a normal test run — matching the
	suite norm where Chrome-backed rendering is not exercised in CI.
	"""
	import shutil

	from frappe.utils.chromium import EXECUTABLE_PATHS

	configured = frappe.get_common_site_config().get("chromium_path", "")
	if configured and shutil.which(configured):
		return True

	import platform
	from pathlib import Path

	executable_name = EXECUTABLE_PATHS.get(platform.system().lower())
	if not executable_name:
		return False
	exec_path = Path(frappe.utils.get_bench_path()).joinpath("chromium", *executable_name)
	return exec_path.exists()


@unittest.skipUnless(is_chromium_available(), "Chromium is not installed")
class TestPreview(IntegrationTestCase):
	"""Native preview-image generation via the headless-Chromium CDP stack.

	These hit real Chromium, so they only run when it is already installed.
	"""

	HTML = (
		"<html><body style='margin:0'>"
		"<div style='width:100%;height:200px;background:#16a34a'>preview</div>"
		"</body></html>"
	)

	def assert_image(self, data: bytes, expected_format: str):
		self.assertTrue(data, "no image bytes returned")
		img = Image.open(BytesIO(data))
		self.assertEqual(img.format, expected_format)
		# default viewport mirrors the old Playwright generator
		self.assertEqual(img.size, (1280, 720))

	def test_get_preview_from_html_jpeg(self):
		from frappe.utils.preview import get_preview_from_html

		self.assert_image(get_preview_from_html(self.HTML, format="jpg"), "JPEG")

	def test_get_preview_from_html_webp(self):
		from frappe.utils.preview import get_preview_from_html

		self.assert_image(get_preview_from_html(self.HTML, format="webp"), "WEBP")

	def test_get_preview_from_url_renders_content(self):
		"""URL navigation must load real content, not the empty navigation stub
		used by the HTML flow."""
		from frappe.utils.preview import get_preview_from_url

		data_url = (
			"data:text/html,<html><body style='margin:0;background:%23dc2626'>"
			"<h1 style='color:white'>nav</h1></body></html>"
		)
		data = get_preview_from_url(data_url, format="jpg")
		self.assert_image(data, "JPEG")
		# A blank navigation stub renders as near-uniform white (a handful of
		# colors); a real page render has many. Asserting on colour variety keeps
		# this robust against jpeg compression noise.
		colors = Image.open(BytesIO(data)).convert("RGB").getcolors(maxcolors=1 << 20)
		self.assertGreater(len(colors or []), 100)


class TestPreviewValidation(IntegrationTestCase):
	"""Format validation raises before Chromium is touched, so it runs everywhere."""

	def test_invalid_format_raises(self):
		from frappe.utils.preview import get_preview_from_html

		with self.assertRaises(frappe.ValidationError):
			get_preview_from_html("<html></html>", format="png")
