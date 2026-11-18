# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Native HTML/URL preview-image generation.

Renders with the bundled headless-Chromium + CDP stack that already powers PDF
generation — no Playwright/Selenium dependency or external service. Plain
in-process helpers (call them directly, e.g. from Builder); deliberately not
whitelisted, since rendering arbitrary HTML/URLs server-side is an SSRF surface.
"""

import asyncio
import time

import frappe
from frappe import _
from frappe.utils.data import cint

SUPPORTED_FORMATS = ("jpg", "jpeg", "webp")
MAX_FULL_PAGE_HEIGHT = 16383


def get_preview_from_html(html: str, format: str = "jpg", width: int = 1280, height: int = 720) -> bytes:
	"""Screenshot a raw HTML string and return the image bytes.

	Args:
	        html: The raw HTML to render and capture.
	        format: Image format — one of ``SUPPORTED_FORMATS`` (jpg, jpeg, webp).
	        width: Viewport width in pixels (default 1280). Set this to the rendered
	                content's width (e.g. a print sheet's pixel width) so the capture
	                isn't cropped or letterboxed.
	        height: Viewport height in pixels (default 720).

	Returns the captured image as bytes, sized to the given viewport.
	"""
	return capture_screenshot(format, html=html, width=width, height=height)


def get_preview_from_url(
	url: str,
	wait_for: int = 0,
	headers: dict | None = None,
	format: str = "jpg",
	width: int = 1280,
	height: int = 720,
	full_page: bool = False,
	wait_until: str | None = None,
	timeout: int = 30,
) -> bytes:
	"""Screenshot a rendered URL and return the image bytes.

	Args:
	        url: The page to load.
	        wait_for: Milliseconds to sleep after the page is ready, before the capture.
	        headers: Extra HTTP headers sent with the page's requests to the URL's own origin,
	                not to other origins it loads from.
	        format: Image format — one of ``SUPPORTED_FORMATS`` (jpg, jpeg, webp).
	        width: Viewport width in pixels (default 1280).
	        height: Viewport height in pixels (default 720).
	        full_page: Capture the document's full scroll height, not only the viewport,
	                capped at ``MAX_FULL_PAGE_HEIGHT`` pixels. Content inside an inner scroll
	                container (e.g. a ``100vh`` app shell) is not expanded.
	        wait_until: A synchronous JavaScript expression, polled until it is truthy
	                before the capture, instead of waiting for the network to go idle.
	                It is checked at least once. A syntax error in it raises at once.
	        timeout: Seconds to wait for the page load and ``wait_until`` when ``wait_until``
	                is given; raises ``TimeoutError`` when it is still falsy after that.
	"""
	if wait_until and cint(timeout) <= 0:
		raise ValueError("timeout must be a positive number of seconds")
	return capture_screenshot(
		format,
		url=url,
		wait_for=cint(wait_for),
		headers=headers,
		width=cint(width),
		height=cint(height),
		full_page=full_page,
		wait_until=wait_until,
		timeout=cint(timeout),
	)


def get_image_format(format: str) -> str:
	if format not in SUPPORTED_FORMATS:
		frappe.throw(_("Invalid format. Supported formats are {0}").format(", ".join(SUPPORTED_FORMATS)))
	return "jpeg" if format == "jpg" else format  # Chrome captures jpeg/webp natively


def capture_screenshot(
	format,
	*,
	html=None,
	url=None,
	wait_for=0,
	headers=None,
	width=1280,
	height=720,
	full_page=False,
	wait_until=None,
	timeout=30,
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
					page.set_extra_headers_for_origin(url, headers)
				deadline = time.monotonic() + timeout
				if wait_until:
					page.navigate(url, wait_for=["DOMContentLoaded"], timeout=timeout)
				else:
					page.navigate(url)
				if wait_until:
					wait_until_truthy(page, wait_until, deadline, timeout)
				if wait_for:
					sleep(page, wait_for / 1000)

			clip = get_full_page_clip(page, width) if full_page else None
			return page.capture_screenshot(image_format=image_format, clip=clip)
		finally:
			# Remove the browser before the outer except resets the singleton.
			safe_execute(page and page.close)
			safe_execute(session and session.disconnect)
			generator.remove_browser(browser_id)
	except Exception:
		# Only reset the singleton when the local Chrome process has actually exited.
		# - proc is None: external chromium_websocket_url is in use — no local process
		#   to check; transient network errors must not reset the singleton.
		# - proc.poll() is None: local process is still running — error is application-level.
		proc = generator._chromium_process
		if proc is not None and proc.poll() is not None:
			generator._close_browser()
		raise


def wait_until_truthy(page, expression: str, deadline: float, timeout: int):
	while True:
		remaining = max(deadline - time.monotonic(), 0.5)
		try:
			result, _error = page.send(
				"Runtime.evaluate",
				{"expression": f"Boolean({expression})", "timeout": remaining * 1000},
				timeout=remaining,
			)
		except TimeoutError:
			result = None
		result = result or {}
		if result.get("result", {}).get("value") is True:
			return
		exception = result.get("exceptionDetails", {}).get("exception", {})
		if exception.get("className") == "SyntaxError":
			raise SyntaxError(f"Invalid wait_until expression: {exception.get('description')}")
		if time.monotonic() >= deadline:
			raise TimeoutError(f"Page not ready after {timeout} seconds: {expression} is not truthy")
		sleep(page, 0.1)


def sleep(page, seconds: float):
	"""Sleep while still answering the page's intercepted requests."""
	page.session.loop.run_until_complete(asyncio.sleep(seconds))


def get_full_page_clip(page, width: int) -> dict:
	result, error = page.send("Page.getLayoutMetrics")
	if error:
		raise RuntimeError(f"Error getting layout metrics: {error}")
	content_height = result["cssContentSize"]["height"]
	return {
		"x": 0,
		"y": 0,
		"width": width,
		"height": min(content_height, MAX_FULL_PAGE_HEIGHT),
		"scale": 1,
	}


def safe_execute(fn):
	if fn:
		try:
			fn()
		except Exception:
			frappe.log_error("Preview cleanup failed")
