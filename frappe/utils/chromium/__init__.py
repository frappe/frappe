"""Headless-Chromium toolkit powered by Playwright.

Manages a Chromium subprocess singleton (:class:`ChromiumManager`) and drives
it via Playwright for PDF generation and screenshot previews.  The Playwright
connection is established lazily on the first :meth:`~ChromiumManager.new_context`
call so Chrome startup cost is paid only when needed.

:class:`CDPSocketClient` is kept for backward compatibility (print_designer uses
it directly) but is no longer used internally.
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
