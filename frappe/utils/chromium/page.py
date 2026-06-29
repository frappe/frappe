import base64
import os
import urllib.parse

import frappe
from frappe.utils.pdf import get_host_url

"""
Playwright-based page driver for PDF generation and screenshots.

Replaces the custom CDP Page class. Each Page wraps a Playwright Page object
created from a BrowserContext (via ChromiumManager.new_context()). Cleanup is
handled automatically: context.close() closes all pages within the context.
"""


class Page:
	def __init__(self, pw_page, page_type):
		self._page = pw_page
		self.type = page_type
		self.is_print_designer = False
		self.options = {}
		self._cached_pdf = None
		self._page.emulate_media(media="print")

	def send(self, method, params=None, return_future=False):
		"""Shim for legacy CDP send() calls. Only Network.setExtraHTTPHeaders is handled."""
		if params is None:
			params = {}
		if method == "Network.setExtraHTTPHeaders":
			self._page.set_extra_http_headers(params.get("headers", {}))
		return None, None

	def set_media_emulation(self, media_type="print"):
		self._page.emulate_media(media=media_type)

	def set_device_metrics(self, width=1280, height=720, scale_factor=1):
		self._page.set_viewport_size({"width": width, "height": height})

	def set_tab_url(self, url):
		"""Navigate to url with empty body to establish the page origin."""
		self._page.route(url, lambda route: route.fulfill(status=200, body=""))
		self._page.goto(url, wait_until="load")
		self._page.unroute(url)
		self.wait_for_navigate = lambda: None

	def navigate(self, url, wait_for=None):
		"""Navigate to a real URL and wait for it to load."""
		self._page.goto(url, wait_until="load")

	def set_content(self, html):
		"""Set page HTML content. Routes local asset/file requests from disk."""
		self._setup_local_resource_route()
		self._page.set_content(html, wait_until="load")
		self.wait_for_set_content = lambda: None

	def _setup_local_resource_route(self):
		"""Intercept all requests and serve local assets from disk; abort everything else.

		Every request must be resolved deterministically (fulfill or abort) so
		the page load event fires promptly. Calling route.continue_() for
		external URLs makes real outbound HTTP requests — if a CDN or font host
		is unreachable the request hangs and set_content() times out.

		Security: only paths inside bench sites/assets and site public root are
		served. All other paths and all external URLs are aborted immediately.
		"""
		bench_sites = os.path.abspath(os.path.join(frappe.utils.get_bench_path(), "sites"))
		asset_path = os.path.abspath(os.path.join(bench_sites, "assets"))
		site_public_root = os.path.realpath(frappe.utils.get_site_path("public"))

		def handle_route(route):
			url = route.request.url

			if not url.startswith(get_host_url()):
				# External URLs (CDN fonts, images, analytics, etc.) are not needed
				# for PDF generation and must not be fetched — they can hang forever.
				route.abort("failed")
				return

			path = url.replace(get_host_url(), "").split("?v", 1)[0]
			clean_path = urllib.parse.unquote(path)

			if clean_path.startswith("assets/"):
				final_path = os.path.abspath(os.path.join(bench_sites, clean_path))
				is_safe = os.path.commonpath([final_path, asset_path]) == asset_path
			else:
				final_path = os.path.realpath(os.path.join(site_public_root, clean_path))
				is_safe = os.path.commonpath([final_path, site_public_root]) == site_public_root

			if is_safe and os.path.isfile(final_path):
				content = frappe.read_file(final_path, as_base64=True)
				headers = {}
				if path.endswith(".svg"):
					headers["Content-Type"] = "image/svg+xml"
				if content:
					route.fulfill(status=200, body=base64.b64decode(content), headers=headers)
					return

			if path:
				frappe.log_error(
					title="Attempted Unauthorized File Access in PDF Generator",
					message=f"Blocked access to: {path}\nResolved Path to: {final_path}",
				)
			route.abort("accessdenied")

		self._page.route("**/*", handle_route)

	def evaluate(self, expression, await_promise=False):
		"""Evaluate JS expression. Returns CDP-style dict for call-site compatibility."""
		result = self._page.evaluate(expression)
		return {"result": {"value": result}}

	def get_element_height(self, selector="body"):
		if not self.is_print_designer:
			selector = ".wrapper"

		js = f"""(function() {{
			var wrapper = document.querySelector('{selector}');
			if (!wrapper) return 0;
			var h = wrapper.getBoundingClientRect().height;
			if (h > 0) return Math.ceil(h);
			var top = wrapper.getBoundingClientRect().top;
			var maxBottom = top;
			var nodes = wrapper.querySelectorAll('*');
			for (var i = 0; i < nodes.length; i++) {{
				var pos = window.getComputedStyle(nodes[i]).position;
				if (pos === 'absolute' || pos === 'fixed') continue;
				var b = nodes[i].getBoundingClientRect().bottom;
				if (b > maxBottom) maxBottom = b;
			}}
			return Math.ceil(maxBottom - top);
		}})()"""
		try:
			result = self.evaluate(js)
			height = result.get("result", {}).get("value", 0) or 0
		except Exception:
			height = 0
		return height

	def generate_pdf(self, wait_for_pdf=True, raw=False):
		"""Generate PDF from the current page.

		wait_for_pdf=False caches the result for later retrieval via
		get_pdf_from_stream() — matches the async CDP pattern used by browser.py
		for header/footer optimization (now executed synchronously).
		"""
		from io import BytesIO

		from pypdf import PdfReader

		pdf_bytes = self._page.pdf(**self._build_pdf_options())

		if not wait_for_pdf:
			self._cached_pdf = pdf_bytes
			return

		if raw:
			return pdf_bytes
		return PdfReader(BytesIO(pdf_bytes))

	def get_cached_pdf(self, raw=False):
		"""Retrieve the PDF pre-generated by generate_pdf(wait_for_pdf=False)."""
		from io import BytesIO

		from pypdf import PdfReader

		if raw:
			return self._cached_pdf
		return PdfReader(BytesIO(self._cached_pdf))

	def _build_pdf_options(self):
		"""Convert browser.py options dict to Playwright page.pdf() kwargs."""
		opts = self.options
		pw_opts = {
			"print_background": opts.get("printBackground", True),
			"landscape": opts.get("landscape", False),
			"scale": float(opts.get("scale", 1)),
			"margin": {
				"top": f"{opts.get('marginTop', 0)}in",
				"bottom": f"{opts.get('marginBottom', 0)}in",
				"left": f"{opts.get('marginLeft', 0)}in",
				"right": f"{opts.get('marginRight', 0)}in",
			},
		}
		if opts.get("paperWidth"):
			pw_opts["width"] = f"{opts['paperWidth']}in"
		if opts.get("paperHeight"):
			pw_opts["height"] = f"{opts['paperHeight']}in"
		if opts.get("pageRanges"):
			pw_opts["page_ranges"] = opts["pageRanges"]
		if opts.get("generateTaggedPDF"):
			pw_opts["tagged_pdf"] = True
		if opts.get("generateOutline"):
			pw_opts["outline"] = True
		return pw_opts

	def capture_screenshot(self, image_format="jpeg", quality=30):
		"""Screenshot the current viewport; returns raw image bytes."""
		kwargs = {"type": image_format, "full_page": False}
		if image_format in ("jpeg", "webp"):
			kwargs["quality"] = quality
		return self._page.screenshot(**kwargs)

	def close(self):
		self._page.close()
