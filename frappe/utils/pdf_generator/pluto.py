import base64
import copy
import importlib.util
import mimetypes
import re
from io import BytesIO

import frappe
from frappe import _
from frappe.utils import cstr, format_date, format_time, now_datetime
from frappe.utils.pdf import get_host_url
from frappe.utils.pdf_generator.browser import Browser

POINTS_PER_INCH = 72
POINTS_PER_PX = 0.75
VIEWPORT_WIDTH = 800
SCRIPT = re.compile(r"<script|\son[a-z]+\s*=", re.IGNORECASE)
JINJA_TAG = re.compile(r"{%.*?%}|{{.*?}}|{#.*?#}", re.DOTALL)
BASE_STYLE = (
	"@page { size: auto !important; margin: auto !important; } * { font-variant-ligatures: no-contextual; }"
)
CSS_IN_HTML = re.compile(
	r"(<style\b[^>]*>.*?</style>|\sstyle\s*=\s*(?:\"[^\"]*\"|'[^']*'))", re.IGNORECASE | re.DOTALL
)
CONTAINER_QUERY = re.compile(
	r"@container\s*\(\s*(min|max)-width\s*:\s*([\d.]+)\s*(px|mm|cm|in|pt)\s*\)", re.IGNORECASE
)
PX_PER_UNIT = {"px": 1, "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96, "pt": 96 / 72}
MEASURE_STYLE = "html, body, .print-format { height: auto !important; min-height: 0 !important; }"
USER_SCRIPT = re.compile(r"<script(?![^>]*(data-frappe-print|/print\.bundle\.))", re.IGNORECASE)
GRID = re.compile(r"display\W+(inline-)?grid\b", re.IGNORECASE)
INTER_WOFF2_HINT = re.compile(
	r"""(url\(["']?/assets/frappe/css/fonts/inter/[^)]*\))\s*format\(["']woff2["']\)"""
)


def resolve_container_queries(css: str, width: float) -> str:
	def resolve(query):
		limit = float(query.group(2)) * PX_PER_UNIT[query.group(3).lower()]
		matches = width >= limit if query.group(1).lower() == "min" else width <= limit
		return "@media all" if matches else "@media not all"

	return CONTAINER_QUERY.sub(resolve, css)


def plutoprint_can_render(html: str) -> bool:
	if importlib.util.find_spec("plutoprint") is None:
		return False
	html = html or ""
	if "data-barcode-value=" in html or USER_SCRIPT.search(html):
		return False
	return not GRID.search(html)


def plutoprint_blockers(print_format=None) -> list[str]:
	blockers = []
	if importlib.util.find_spec("plutoprint") is None:
		blockers.append(_("PlutoPrint is not installed on this server"))
	if print_format:
		if print_format.get("print_designer"):
			blockers.append(_("Print Designer"))
		source = "\n".join(cstr(print_format.get(field)) for field in ("html", "css", "format_data"))
		if SCRIPT.search(JINJA_TAG.sub("", source)):
			blockers.append(_("JavaScript"))
		if GRID.search(source):
			blockers.append(_("CSS grid"))
	return blockers


class PlutoBrowser(Browser):
	def __init__(self, print_format, html, options):
		super().__init__(self, print_format, html, options)

	def add_browser(self, browser_id):
		pass

	def remove_browser(self, browser_id):
		pass

	def open(self, generator):
		pass

	def close(self):
		pass

	def detach_debug_browser(self):
		pass

	def new_page(self, page_type):
		if not hasattr(self, "fetcher"):
			self.fetcher = local_resource_fetcher(bool(self.options.get("block-external-requests")))
		page = PlutoPage(page_type, self.fetcher)
		page.is_print_designer = self.is_print_designer
		return page

	def update_header_footer_page(self):
		if not self.header_page and not self.footer_page:
			return
		total_pages = len(self.body_pdf.pages)
		if self.header_page and self.is_header_dynamic:
			self.header_page.repeat_for_pages(total_pages)
		if self.footer_page and self.is_footer_dynamic:
			self.footer_page.repeat_for_pages(total_pages)


class PlutoPage:
	def __init__(self, page_type, fetcher):
		self.type = page_type
		self.fetcher = fetcher
		self.options = {}
		self.html = ""
		self.viewport_width = VIEWPORT_WIDTH

	def send(self, method, params=None):
		return None, None

	def set_tab_url(self, url):
		pass

	def wait_for_navigate(self):
		pass

	def set_content(self, html, wait_for=None):
		self.html = html

	def wait_for_set_content(self):
		pass

	def set_device_metrics(self, width=VIEWPORT_WIDTH, height=720, scale_factor=1):
		self.viewport_width = width

	def get_content_width(self):
		return self._book(self.viewport_width * POINTS_PER_PX, None).get_document_width()

	def get_content_height(self):
		self.html += f"<style>{MEASURE_STYLE}</style>"
		return self._book(self.viewport_width * POINTS_PER_PX, None).get_document_height()

	def get_element_height(self, selector="body"):
		book = self._book(self.viewport_width * POINTS_PER_PX, None, user_style=MEASURE_STYLE)
		return book.get_document_height()

	def repeat_for_pages(self, total_pages):
		from bs4 import BeautifulSoup

		soup = BeautifulSoup(self.html, "html5lib")
		if not (template := soup.select_one(".wrapper")):
			return
		now = now_datetime()
		values = {
			"topage": total_pages,
			"date": format_date(now),
			"isodate": now.isoformat(),
			"time": format_time(now),
		}
		original = copy.copy(template)
		previous = template
		for page_no in range(1, total_pages + 1):
			wrapper = template if page_no == 1 else copy.copy(original)
			for class_name, value in {**values, "page": page_no}.items():
				for element in wrapper.select(f".{class_name}"):
					element.string = cstr(value)
			hidden_on_this_page = [".hidden-first-page" if page_no == 1 else ".visible-first-page"]
			if page_no != total_pages:
				hidden_on_this_page.append(".visible-last-page")
			for element in wrapper.select(",".join(hidden_on_this_page)):
				element["style"] = f"{element.get('style', '')};visibility: hidden"
			if page_no > 1:
				previous.insert_after(wrapper)
				previous = wrapper
		self.html = str(soup)

	def generate_pdf(self, wait_for_pdf=True, raw=False):
		if not wait_for_pdf:
			return
		from pypdf import PdfReader

		options = self.options
		width = options["paperWidth"] * POINTS_PER_INCH
		height = options["paperHeight"] * POINTS_PER_INCH
		margins = [
			options.get(side, 0) * POINTS_PER_INCH
			for side in ("marginTop", "marginRight", "marginBottom", "marginLeft")
		]
		scale = options.get("scale") or 1
		book = self._book(width, height, margins, f"@page {{ -pluto-page-scale: {scale}; }}")
		stream = BytesIO()
		book.write_to_pdf_stream(stream)
		return stream.getvalue() if raw else PdfReader(stream)

	def get_pdf_stream_id(self):
		return None

	def get_pdf_from_stream(self, stream_id, raw=False):
		return self.generate_pdf(raw=raw)

	def close(self):
		self.html = ""

	def _book(self, width, height, margins=None, user_style=""):
		import plutoprint

		height = height or 100000
		margins = margins or (0, 0, 0, 0)
		book = plutoprint.Book(
			plutoprint.PageSize(width, height), plutoprint.PageMargins(*margins), plutoprint.MEDIA_TYPE_PRINT
		)
		book.custom_resource_fetcher = self.fetcher
		content_width = (width - margins[1] - margins[3]) / POINTS_PER_PX
		html = CSS_IN_HTML.sub(lambda css: resolve_container_queries(css.group(0), content_width), self.html)
		book.load_html(html, user_style=BASE_STYLE + user_style, base_url=get_host_url())
		return book


def local_resource_fetcher(block_external_requests=False):
	import plutoprint
	from werkzeug.http import parse_options_header

	from frappe.core.api.file import get_max_file_size
	from frappe.utils.chromium.page import (
		allows_internal_print_urls,
		read_external_resource,
		read_local_resource,
	)

	class Fetcher(plutoprint.ResourceFetcher):
		def __init__(self):
			super().__init__()
			self.cache = {}

		def fetch_url(self, url):
			if url not in self.cache:
				try:
					self.cache[url] = self.fetch(url)
				except plutoprint.Error as error:
					self.cache[url] = error
			if isinstance(self.cache[url], plutoprint.Error):
				raise self.cache[url]
			return self.cache[url]

		def fetch(self, url):
			if url.lower().startswith("file:"):
				raise plutoprint.Error(f"Blocked {url}")
			if url.startswith(get_host_url()):
				if not (resource := read_local_resource(url)):
					raise plutoprint.Error(f"Cannot read {url}")
				content, content_type = resource
				content_type = (
					content_type or mimetypes.guess_type(url.split("?")[0])[0] or "application/octet-stream"
				)
				if content_type == "text/css":
					content = INTER_WOFF2_HINT.sub(r"\1", base64.b64decode(content).decode()).encode()
					content = base64.b64encode(content).decode()
				return plutoprint.default_resource_fetcher.fetch_url(f"data:{content_type};base64,{content}")
			if block_external_requests and not url.startswith("data:"):
				raise plutoprint.Error(f"Blocked {url}")
			if url.startswith("data:") or allows_internal_print_urls():
				resource = plutoprint.default_resource_fetcher.fetch_url(url)
			elif external := read_external_resource(url, get_max_file_size(), {"User-Agent": "Mozilla/4.0"}):
				content, headers, _status_code = external
				mime_type, options = parse_options_header(headers.get("Content-Type"))
				resource = plutoprint.ResourceData(
					content,
					mime_type or mimetypes.guess_type(url.split("?")[0])[0] or "application/octet-stream",
					options.get("charset", ""),
				)
			else:
				raise plutoprint.Error(f"Cannot read {url}")
			if resource.get_mime_type() == "text/html":
				raise plutoprint.Error(f"Not a page resource: {url}")
			return resource

	return Fetcher()
