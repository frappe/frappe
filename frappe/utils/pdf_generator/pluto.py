import base64
import copy
import importlib.util
import mimetypes
import os
import re
from io import BytesIO
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import cstr, format_date, format_time, now_datetime
from frappe.utils.pdf import get_host_url
from frappe.utils.pdf_generator.browser import Browser

POINTS_PER_INCH = 72
POINTS_PER_PX = 0.75
VIEWPORT_WIDTH = 800
MAX_SHRINK = 0.5
SCRIPT = re.compile(r"<script|\son[a-z]+\s*=", re.IGNORECASE)
BASE_STYLE = "* { font-variant-ligatures: no-contextual; }"
BREAK_WORD = re.compile(r"((?:overflow|word)-wrap\s*:\s*)(?:break-word|anywhere)", re.IGNORECASE)
CSS_IN_HTML = re.compile(
	r"(<style\b[^>]*>.*?</style>|\sstyle\s*=\s*(?:\"[^\"]*\"|'[^']*'))", re.IGNORECASE | re.DOTALL
)
CONTAINER_QUERY = re.compile(
	r"@container\s*\(\s*(min|max)-width\s*:\s*([\d.]+)\s*(px|mm|cm|in|pt)\s*\)", re.IGNORECASE
)
PX_PER_UNIT = {"px": 1, "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96, "pt": 96 / 72}
MULTI_PAGE_STYLE = (
	"body, .row:has(> :only-child) { display: block !important; padding-top: 0.02px; padding-bottom: 0.02px; }"
	".row:has(> :nth-child(2)), .section:has(> .section-label + .row > :nth-child(2)) { break-inside: avoid; }"
)
MEASURE_STYLE = "html, body, .print-format { height: auto !important; min-height: 0 !important; }"
USER_SCRIPT = re.compile(r"<script(?![^>]*(data-frappe-print|/print\.bundle\.))", re.IGNORECASE)
LETTER_HEAD_STYLE = re.compile(r"<style data-letter-head>(.*?)</style>", re.IGNORECASE | re.DOTALL)
GRID = re.compile(r"display\W+(inline-)?grid\b", re.IGNORECASE)
INTER_WOFF2 = re.compile(r"/assets/frappe/css/fonts/inter/Inter-(\w+)\.woff2")
FONT_FACE = re.compile(r"@font-face\s*\{[^}]*\}", re.IGNORECASE)
INTER_WOFF2_HINT = re.compile(
	r"""(url\(["']?/assets/frappe/css/fonts/inter/[^)]*\))\s*format\(["']woff2["']\)"""
)
INTER_WEIGHTS = {
	"Thin": 100,
	"ExtraLight": 200,
	"Light": 300,
	"Medium": 500,
	"SemiBold": 600,
	"Bold": 700,
	"ExtraBold": 800,
	"Black": 900,
}


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
	return not any(GRID.search(css) for css in LETTER_HEAD_STYLE.findall(html))


def plutoprint_blockers(print_format=None) -> list[str]:
	blockers = []
	if importlib.util.find_spec("plutoprint") is None:
		blockers.append(_("PlutoPrint is not installed on this server"))
	if print_format:
		source = "\n".join(cstr(print_format.get(field)) for field in ("html", "css", "format_data"))
		if SCRIPT.search(source):
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

	def get_element_height(self, selector="body"):
		book = self._book(self.viewport_width * POINTS_PER_PX, None, user_style=MEASURE_STYLE)
		return round(book.get_document_height())

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
		previous = template
		for page_no in range(1, total_pages + 1):
			wrapper = template if page_no == 1 else copy.copy(template)
			for class_name, value in {**values, "page": page_no}.items():
				for element in wrapper.select(f".{class_name}"):
					element.string = cstr(value)
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
		book = self._layout(width, height, margins, scale)
		content_width = width - margins[1] - margins[3]
		overflow = book.get_document_width() * POINTS_PER_PX * scale
		if overflow > content_width + 1:
			scale *= max(content_width / overflow, MAX_SHRINK)
			book = self._layout(width, height, margins, scale)
		if book.get_page_count() > 1:
			book = self._layout(width, height, margins, scale, MULTI_PAGE_STYLE)

		pdf = self._write(book, width, height, scale)
		return pdf if raw else PdfReader(BytesIO(pdf))

	def get_pdf_stream_id(self):
		return None

	def get_pdf_from_stream(self, stream_id, raw=False):
		return self.generate_pdf(raw=raw)

	def close(self):
		self.html = ""

	def _layout(self, width, height, margins, scale, user_style=""):
		return self._book(
			width / scale, height / scale, [margin / scale for margin in margins], user_style=user_style
		)

	def _book(self, width, height, margins=None, user_style=""):
		import plutoprint

		height = height or 100000
		margins = margins or (0, 0, 0, 0)
		page_rule = "<style>@page {{ size: {}pt {}pt; margin: {}pt {}pt {}pt {}pt; }}</style>".format(
			width, height, *margins
		)
		book = plutoprint.Book(
			plutoprint.PageSize(width, height), plutoprint.PageMargins(*margins), plutoprint.MEDIA_TYPE_PRINT
		)
		book.custom_resource_fetcher = self.fetcher
		content_width = (width - margins[1] - margins[3]) / POINTS_PER_PX
		html = CSS_IN_HTML.sub(
			lambda css: resolve_container_queries(BREAK_WORD.sub(r"\1normal", css.group(0)), content_width),
			self.html,
		)
		book.load_html(
			html + page_rule,
			user_style=BASE_STYLE + user_style,
			base_url=get_host_url(),
		)
		return book

	def _write(self, book, width, height, scale):
		import plutoprint

		stream = BytesIO()
		if scale == 1:
			book.write_to_pdf_stream(stream)
			return stream.getvalue()
		canvas = plutoprint.PDFCanvas.create_for_stream(stream, plutoprint.PageSize(width, height))
		for index in range(book.get_page_count()):
			canvas.save_state()
			canvas.scale(scale * POINTS_PER_PX, scale * POINTS_PER_PX)
			book.render_page(canvas, index)
			canvas.restore_state()
			canvas.show_page()
		canvas.finish()
		return stream.getvalue()


def inter_ttf_path(url: str) -> Path | None:
	from frappe.utils.typst_emitter import DEFAULT_FONT, _font_cache_path, ensure_typst_fonts

	if not (match := INTER_WOFF2.search(url)) or match.group(1).endswith("Italic"):
		return None
	if not (path := _font_cache_path(DEFAULT_FONT)):
		ensure_typst_fonts(None)
		return None
	weight = INTER_WEIGHTS.get(match.group(1), 400)
	return next((Path(path, name) for name in os.listdir(path) if name.endswith(f"-{weight}.ttf")), None)


def cached_inter_faces(css: str) -> str:
	if not INTER_WOFF2.search(css):
		return css
	css = FONT_FACE.sub(
		lambda face: (
			face.group(0) if not INTER_WOFF2.search(face.group(0)) or inter_ttf_path(face.group(0)) else ""
		),
		css,
	)
	return INTER_WOFF2_HINT.sub(r"\1", css)


def local_resource_fetcher(block_external_requests=False):
	import plutoprint

	from frappe.utils.chromium.page import read_local_resource

	class Fetcher(plutoprint.ResourceFetcher):
		def __init__(self):
			super().__init__()
			self.cache = {}

		def fetch_url(self, url):
			if url not in self.cache:
				self.cache[url] = self.fetch(url)
			return self.cache[url]

		def fetch(self, url):
			if url.startswith(get_host_url()):
				if ttf := inter_ttf_path(url):
					return plutoprint.ResourceData(ttf.read_bytes(), "font/ttf")
				if not (resource := read_local_resource(url)):
					raise plutoprint.Error(f"Cannot read {url}")
				content, content_type = resource
				content = base64.b64decode(content)
				content_type = (
					content_type or mimetypes.guess_type(url.split("?")[0])[0] or "application/octet-stream"
				)
				if content_type == "text/css":
					content = cached_inter_faces(BREAK_WORD.sub(r"\1normal", content.decode())).encode()
				return plutoprint.ResourceData(content, content_type)
			if block_external_requests and not url.startswith("data:"):
				raise plutoprint.Error(f"Blocked {url}")
			resource = plutoprint.default_resource_fetcher.fetch_url(url)
			if resource.get_mime_type() == "text/html":
				raise plutoprint.Error(f"Not a page resource: {url}")
			return resource

	return Fetcher()
