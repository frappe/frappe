"""Generic headless-Chromium toolkit driven over the Chrome DevTools Protocol.

This is the general-purpose "spin up headless chrome and drive a page" stack:
a singleton process manager (:class:`ChromiumManager`), a CDP websocket client
(:class:`CDPSocketClient`), a :class:`Page` driver, and the binary download/setup
helpers. It powers PDF generation (``frappe.utils.pdf_generator``) and screenshot
previews (``frappe.utils.preview``), and can be used directly for browser
automation such as scraping.
"""

from frappe.utils.chromium.cdp_connection import CDPSocketClient
from frappe.utils.chromium.download import (
	EXECUTABLE_PATHS,
	calculate_platform,
	download_chromium,
	find_or_download_chromium_executable,
	get_chromium_download_url,
	get_linux_distribution_info,
	make_chromium_executable,
	setup_chromium,
)
from frappe.utils.chromium.page import Page
from frappe.utils.chromium.process import ChromiumManager

__all__ = [
	"EXECUTABLE_PATHS",
	"CDPSocketClient",
	"ChromiumManager",
	"Page",
	"calculate_platform",
	"download_chromium",
	"find_or_download_chromium_executable",
	"get_chromium_download_url",
	"get_linux_distribution_info",
	"make_chromium_executable",
	"setup_chromium",
]
