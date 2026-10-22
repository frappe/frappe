# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import sys
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase
from frappe.utils.print_utils import get_chromium_download_url


class TestChromiumDownload(UnitTestCase):
	def test_linux_arm64_download_url_on_amazon_linux(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")

		with (
			patch("platform.system", return_value="Linux"),
			patch("platform.machine", return_value="aarch64"),
			patch.dict(sys.modules, {"distro": SimpleNamespace(id=lambda: "amzn", version=lambda: "2023")}),
			patch("frappe.get_common_site_config", return_value={}),
		):
			url = get_chromium_download_url()

		self.assertTrue(url.endswith("/chromium-headless-shell-linux-arm64.zip"), url)
