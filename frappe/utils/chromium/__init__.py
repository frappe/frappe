"""Headless-Chromium toolkit powered by Playwright.

:class:`ChromiumManager` launches and manages a Chromium browser via Playwright.
:meth:`~ChromiumManager.new_context` creates isolated browser contexts; each
context.close() cleans up all pages automatically.

Run ``bench setup-chrome`` once to install Chromium (``playwright install chromium
--with-deps``).  In Docker, run it during the image build so the layer is cached.

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
