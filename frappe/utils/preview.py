# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Native HTML/URL preview-image generation.

Renders with the bundled headless-Chromium + CDP stack that already powers PDF
generation — no Playwright/Selenium dependency or external service. Plain
in-process helpers (call them directly, e.g. from Builder); deliberately not
whitelisted, since rendering arbitrary HTML/URLs server-side is an SSRF surface.
"""

import time

import frappe
from frappe import _
from frappe.utils.data import cint

SUPPORTED_FORMATS = ("jpg", "jpeg", "webp")


def get_preview_from_html(html: str, format: str = "jpg") -> bytes:
	"""Screenshot a raw HTML string; returns viewport-sized image bytes."""
	return capture_screenshot(format, html=html)


def get_preview_from_url(
	url: str, wait_for: int = 0, headers: dict | None = None, format: str = "jpg"
) -> bytes:
	"""Screenshot a rendered URL; returns viewport-sized image bytes."""
	return capture_screenshot(format, url=url, wait_for=cint(wait_for), headers=headers)


def get_image_format(format: str) -> str:
	if format not in SUPPORTED_FORMATS:
		frappe.throw(_("Invalid format. Supported formats are {0}").format(", ".join(SUPPORTED_FORMATS)))
	return "jpeg" if format == "jpg" else format  # Chrome captures jpeg/webp natively


def capture_screenshot(
	format, *, html=None, url=None, wait_for=0, headers=None, width=1280, height=720
) -> bytes:
	"""Drive Chromium over CDP, reusing the PDF generator's process + lifecycle:
	register the browser so Chromium isn't torn down mid-use, and reset the
	singleton on crash so the next request gets a fresh instance."""
	from frappe.utils.pdf import get_host_url
	from frappe.utils.pdf_generator.cdp_connection import CDPSocketClient
	from frappe.utils.pdf_generator.chrome_pdf_generator import ChromePDFGenerator
	from frappe.utils.pdf_generator.page import Page

	image_format = get_image_format(format)
	generator = ChromePDFGenerator()
	browser_id = frappe.utils.random_string(10)
	generator.add_browser(browser_id)
	session = page = None
	try:
		try:
			if not generator._devtools_url:
				generator._set_devtools_url()
			session = CDPSocketClient(generator._devtools_url)
			session.connect()
			context, error = session.send("Target.createBrowserContext", {"disposeOnDetach": True})
			if error:
				raise RuntimeError(f"Error creating browser context: {error}")

			page = Page(session, context["browserContextId"], "screenshot")
			page.is_print_designer = False  # normally set by Browser.new_page
			page.set_media_emulation("screen")  # Page defaults to print media
			page.set_device_metrics(width, height)

			if html is not None:
				# Load the host first so the HTML's local /assets and /files
				# requests are fulfilled from disk by set_content's interceptor.
				page.set_tab_url(get_host_url())
				page.wait_for_navigate()
				page.set_content(html, wait_for=["load", "DOMContentLoaded", "networkIdle"])
				page.wait_for_set_content()
			else:
				if headers:
					page.send("Network.enable")
					page.send("Network.setExtraHTTPHeaders", {"headers": headers})
				page.navigate(url)
				if wait_for:
					time.sleep(wait_for / 1000)

			return page.capture_screenshot(image_format=image_format)
		finally:
			# Remove the browser before the outer except resets the singleton.
			safe_execute(page and page.close)
			safe_execute(session and session.disconnect)
			generator.remove_browser(browser_id)
	except Exception:
		generator._close_browser()  # crashed Chrome → drop the poisoned singleton
		raise


def safe_execute(fn):
	if fn:
		try:
			fn()
		except Exception:
			frappe.log_error("Preview cleanup failed")
