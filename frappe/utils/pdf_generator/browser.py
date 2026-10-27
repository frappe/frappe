import re
from typing import ClassVar

from bs4 import BeautifulSoup

import frappe
from frappe.utils.data import cint, cstr, flt
from frappe.utils.pdf import get_host_url
from frappe.utils.print_utils import _print_format_doc_or_none, convert_uom, parse_float_and_unit

RECEIPT_WIDTHS = {"Receipt 80 mm": "80mm", "Receipt 58 mm": "58mm"}


class Browser:
	def __init__(self, generator, print_format, html, options):
		self.print_format = print_format
		self.is_print_designer = frappe.get_cached_value("Print Format", print_format, "print_designer")
		self.debug_mode = frappe.conf.developer_mode and bool(frappe.form_dict.get("pdf_debug"))
		self.browserID = frappe.utils.random_string(10)
		generator.add_browser(self.browserID)
		try:
			# sets soup from html
			self.set_html(html)
			# sets wkhtmltopdf options
			self.set_options(options)
			# start cdp connection and create browser context ( kind of like new window / incognito mode)
			self.open(generator)
			# opens header and footer pages and sets content ( not waiting for it to load)
			self.prepare_header_footer()
			# opens body page and sets content and waits for it to finshing load
			self.setup_body_page()
			# prepare options as per chrome for pdf
			self.prepare_options_for_pdf()
			# generate header and footer pages if they are not dynamic ( first, odd, even, last)
			self.update_header_footer_page_pd()
			# if header and footer are not dynamic start generating pdf for them (non-blocking)
			self.try_async_header_footer_pdf()
			# now wait for page to load as we need DOM to generate pdf
			self.body_page.wait_for_set_content()
			self.fit_body_height()
			self.body_pdf = self.body_page.generate_pdf(raw=not self.header_page and not self.footer_page)
			self.update_header_footer_page()

			if self.header_page:
				if not self.is_header_dynamic:
					self.header_pdf = self.header_page.get_pdf_from_stream(
						self.header_page.get_pdf_stream_id()
					)
				else:
					self.header_pdf = self.header_page.generate_pdf()

			if self.footer_page:
				if not self.is_footer_dynamic:
					self.footer_pdf = self.footer_page.get_pdf_from_stream(
						self.footer_page.get_pdf_stream_id()
					)
				else:
					self.footer_pdf = self.footer_page.generate_pdf()
		finally:
			if not self.debug_mode:
				for attr in ("body_page", "header_page", "footer_page"):
					page = getattr(self, attr, None)
					if page:
						try:
							page.close()
						except Exception:
							frappe.log_error(f"Failed to close {attr} in Chrome")
				if getattr(self, "session", None):
					try:
						self.close()
					except Exception:
						frappe.log_error("Failed to disconnect CDP session")
			generator.remove_browser(self.browserID)
		if self.debug_mode:
			generator.detach_debug_browser()

	def open(self, generator):
		from frappe.utils.pdf_generator.cdp_connection import CDPSocketClient

		# checking because if we share browser accross request _devtools_url will already be set for subsequent requests.
		if not generator._devtools_url:
			generator._set_devtools_url()
		# start the CDP websocket connection to browser
		self.session = CDPSocketClient(generator._devtools_url)

		self.session.connect()
		self.create_browser_context()

	def create_browser_context(self):
		# create browser context
		result, error = self.session.send("Target.createBrowserContext", {"disposeOnDetach": True})
		if error:
			frappe.log_error(title="Error creating browser context:", message=f"{error}")
		self.browser_context_id = result["browserContextId"]

	def set_html(self, html):
		self.soup = BeautifulSoup(html, "html5lib")

	def set_options(self, options):
		self.options = options

	def new_page(self, page_type):
		"""
		# create a new page in the browser inside browser context
		----
		TODO: Implement Deterministic rendering for headless-chrome via DevTools Protocol ( waiting for macos support )
		https://docs.google.com/document/d/1PppegrpXhOzKKAuNlP6XOEnviXFGUiX2hop00Cxcv4o/edit?tab=t.0#bookmark=id.dukbomwxpb3j

		NOTE: In theory this will make it faster but more importantly use less cpu, ram etc.
		"""

		from frappe.utils.pdf_generator.page import Page

		page = Page(self.session, self.browser_context_id, page_type)
		page.is_print_designer = self.is_print_designer

		return page

	def setup_body_page(self):
		self.body_page = self.new_page("body")
		self.body_page.set_tab_url(get_host_url())
		self.body_page.wait_for_navigate()
		self.body_page.set_content(str(self.soup))

	def fit_body_height(self):
		if not self.options.get("fit-height"):
			return
		options = self.body_page.options
		printable = 96 * (
			options["paperWidth"] - options.get("marginLeft", 0) - options.get("marginRight", 0)
		)
		self.body_page.set_device_metrics(width=int(printable), height=1)
		height = (self.body_page.get_content_height() + 2) * options.get("scale", 1) / 96
		options["paperHeight"] = height + options.get("marginTop", 0) + options.get("marginBottom", 0)

	def close_page(self, type):
		page = getattr(self, f"{type}_page")
		page.close()

	def is_page_no_used(self, soup):
		# Check if any of the classes exist
		classes_to_check = [
			"page",
			"frompage",
			"topage",
			"page_info_page",
			"page_info_frompage",
			"page_info_topage",
		]

		# Loop through the classes to check
		for class_name in classes_to_check:
			if soup.find(class_=class_name):  # Check if any element with the class is found
				return True  # Return True if class is found

		return False

	def prepare_header_footer(self):
		# code is structured like this to improve performance by running commands in chrome as soon as possible.
		soup = self.soup
		options = self.options
		self._add_page_number(soup)
		# open header and footer pages
		self._open_header_footer_pages()

		self._inject_page_no_script(soup)

		# get tags to pass to header template.
		head = soup.find("head").contents
		styles = soup.find_all("style")

		# set header and footer content ( not waiting for it to load yet).
		if self.header_page:
			self.header_page.wait_for_navigate()
			self.header_page.set_content(
				self.get_rendered_header_footer(self.header_content, "header", head, styles, css=[])
			)

		if self.footer_page:
			self.footer_page.wait_for_navigate()
			self.footer_page.set_content(
				self.get_rendered_header_footer(self.footer_content, "footer", head, styles, css=[])
			)
		if self.header_page:
			self.header_page.wait_for_set_content()
			self.header_height = self.header_page.get_element_height()
			self.is_header_dynamic = self.is_page_no_used(self.header_content)
			del self.header_content
		else:
			# bad implicit setting of margin #backwards-compatibility
			options["margin-top"] = "15mm"

		if self.footer_page:
			self.footer_page.wait_for_set_content()
			self.footer_height = self.footer_page.get_element_height()
			self.is_footer_dynamic = self.is_page_no_used(self.footer_content)
			del self.footer_content
		else:
			# bad implicit setting of margin #backwards-compatibility
			options["margin-bottom"] = "15mm"

		# Remove instances of them from main content for render_template
		for html_id in ["header-html", "footer-html"]:
			for tag in soup.find_all(id=html_id):
				tag.extract()

	def _add_page_number(self, soup):
		from frappe.printing.doctype.print_format.classic_converter import uses_beta_renderer
		from frappe.utils.print_format_generator import page_number_html

		if self.is_print_designer or not self.print_format:
			return
		if any(el.find(class_=["page", "topage"]) for el in soup.find_all(id=["header-html", "footer-html"])):
			return
		if not frappe.db.exists("Print Format", self.print_format):
			return
		print_format = frappe.get_cached_doc("Print Format", self.print_format)
		position = (print_format.page_number or "").lower().replace(" ", "_")
		if uses_beta_renderer(print_format) or not position.startswith(("top_", "bottom_")):
			return
		html_id = "header-html" if position.startswith("top_") else "footer-html"
		if not (target := soup.find(id=html_id)):
			target = soup.new_tag("div", id=html_id)
			soup.body.append(target)
		target.append(BeautifulSoup(page_number_html(position), "html.parser"))

	def _inject_page_no_script(self, soup):
		"""Make clone_and_update available to the header and footer pages, which take
		their <head> contents from the body document."""
		path = frappe.get_app_path("frappe", "utils", "pdf_generator", "update_page_no.js")
		tag = soup.new_tag("script")
		tag.append(soup.new_string(frappe.read_file(path)))
		soup.head.append(tag)

	def try_async_header_footer_pdf(self):
		if self.header_page and not self.is_header_dynamic:
			self.header_page.generate_pdf(wait_for_pdf=False)
		if self.footer_page and not self.is_footer_dynamic:
			self.footer_page.generate_pdf(wait_for_pdf=False)

	def _get_converted_num(self, num_str, unit="px"):
		parsed = parse_float_and_unit(num_str)
		if parsed:
			return convert_uom(parsed["value"], parsed["unit"], unit, only_number=True)

	def _parse_pdf_options_from_html(self):
		from frappe.utils.pdf import get_print_format_styles
		from frappe.www.printview import PAGE_LENGTH, PAGE_MARGIN_SIDES

		soup: BeautifulSoup = self.soup
		options = self._get_print_format_page_margins()
		print_format_css = get_print_format_styles(soup)
		attrs = (
			"margin-top",
			"margin-bottom",
			"margin-left",
			"margin-right",
			"page-size",
			"header-spacing",
			"orientation",
			"page-width",
			"page-height",
		)
		options |= {
			style.name: style.value
			for style in print_format_css
			if style.name in attrs
			and (style.name not in PAGE_MARGIN_SIDES or re.fullmatch(f"0|{PAGE_LENGTH}", style.value.strip()))
		}
		self.options.update(options)
		self._set_page_size_from_print_format()
		self._set_page_size_from_page_rule()

	def _set_page_size_from_print_format(self):
		if any(self.options.get(key) for key in ("page-size", "page-width", "page-height")):
			return
		if not self.print_format or not frappe.db.exists("Print Format", self.print_format):
			return
		paper_size = frappe.get_cached_value("Print Format", self.print_format, "paper_size")
		if receipt_width := RECEIPT_WIDTHS.get(paper_size):
			self.options |= {"page-width": receipt_width, "page-height": "297mm", "fit-height": True}
		elif paper_size:
			self.options["page-size"] = paper_size

	def _set_page_size_from_page_rule(self):
		from frappe.www.printview import get_page_rule_size

		if any(self.options.get(key) for key in ("page-size", "page-width", "page-height")):
			return
		css = "".join(cstr(tag.string) for tag in self.soup.find_all("style"))
		for key, value in get_page_rule_size(css).items():
			if not self.options.get(key):
				self.options[key] = value

	def _get_print_format_page_margins(self):
		from frappe.printing.doctype.print_format.classic_converter import uses_beta_renderer
		from frappe.www.printview import get_page_rule_margins

		print_format = _print_format_doc_or_none(self.print_format)
		if (
			not print_format
			or not print_format.css
			or uses_beta_renderer(print_format)
			or print_format.pdf_generator != "chrome"
		):
			return {}
		return get_page_rule_margins(print_format.css)

	def _set_default_page_size(self):
		options = self.options
		pdf_page_size = (
			options.get("page-size") or frappe.db.get_single_value("Print Settings", "pdf_page_size") or "A4"
		)

		if pdf_page_size == "Custom":
			for option, field in (("page-height", "pdf_page_height"), ("page-width", "pdf_page_width")):
				if not options.get(option):
					value = frappe.db.get_single_value("Print Settings", field)
					options[option] = f"{flt(value)}mm" if value else None
		else:
			options["page-size"] = pdf_page_size

	def prepare_options_for_pdf(self):
		self._parse_pdf_options_from_html()
		self._set_default_page_size()

		options = self.options

		updated_options = {
			"scale": 1,
			"printBackground": True,
			"transferMode": "ReturnAsStream",
			"marginTop": 0,
			"marginBottom": 0,
			"marginLeft": 0,
			"marginRight": 0,
			"preferCSSPageSize": False,
			"pageRanges": options.get("page-ranges", ""),
			# Experimental
			"generateTaggedPDF": options.get("generate-tagged-pdf", False),
			"generateOutline": options.get("generate-outline", False),
		}

		# bad implicit setting of margin #backwards-compatibility
		if not self.is_print_designer:
			if not options.get("margin-right"):
				options["margin-right"] = "15mm"

			if not options.get("margin-left"):
				options["margin-left"] = "15mm"

		if not options.get("page-height") or not options.get("page-width"):
			if not (page_size := self.options.get("page-size")):
				raise frappe.ValidationError("Page size is required")
			if page_size == "CUSTOM":
				raise frappe.ValidationError("Custom page size requires page-height and page-width")
			size = PageSize.get(page_size)
			if not size:
				raise frappe.ValidationError("Invalid page size")

			options["page-height"] = convert_uom(size["height"], "mm", "px", only_number=True)
			options["page-width"] = convert_uom(size["width"], "mm", "px", only_number=True)

		if isinstance(options["page-height"], str):
			options["page-height"] = self._get_converted_num(options["page-height"])

		if isinstance(options["page-width"], str):
			options["page-width"] = self._get_converted_num(options["page-width"])

		if (
			cstr(options.get("orientation")).lower() == "landscape"
			and options["page-width"] < options["page-height"]
		):
			options["page-width"], options["page-height"] = options["page-height"], options["page-width"]

		updated_options["paperWidth"] = convert_uom(options["page-width"], "px", "in", only_number=True)

		if options.get("margin-left"):
			updated_options["marginLeft"] = convert_uom(
				self._get_converted_num(options["margin-left"]), "px", "in", only_number=True
			)

		if options.get("margin-right"):
			updated_options["marginRight"] = convert_uom(
				self._get_converted_num(options["margin-right"]), "px", "in", only_number=True
			)

		self.printable_width = 96 * (
			updated_options["paperWidth"] - updated_options["marginLeft"] - updated_options["marginRight"]
		)
		if self.header_page:
			self.header_page.set_device_metrics(width=int(self.printable_width))
			self.header_height = self.header_page.get_element_height()
		if self.footer_page:
			self.footer_page.set_device_metrics(width=int(self.printable_width))
			self.footer_height = self.footer_page.get_element_height()

		# make copy of options to update them in header, body, footer.
		self.body_page.options = updated_options.copy()
		if self.header_page:
			self.header_page.options = updated_options.copy()
		if self.footer_page:
			self.footer_page.options = updated_options.copy()

		margin_top = self._get_converted_num(options.get("margin-top", 0))
		margin_bottom = self._get_converted_num(options.get("margin-bottom", 0))

		header_with_top_margin = 0
		header_with_spacing_top_margin = 0
		footer_with_bottom_margin = 0
		footer_height = 0

		header_owns_top_margin = bool(options.get("header-includes-top-margin"))

		if self.header_page:
			header_with_top_margin = self.header_height + (0 if header_owns_top_margin else margin_top)
			header_spacing = options.get("header-spacing", 0)
			header_with_spacing_top_margin = header_with_top_margin + header_spacing
			self.header_page.options["paperHeight"] = (
				convert_uom(header_with_spacing_top_margin, "px", "in", only_number=True)
				if header_with_spacing_top_margin
				else 0
			)

		margin_top = convert_uom(margin_top, "px", "in", only_number=True)

		if self.header_page:
			self.header_page.options["marginTop"] = 0 if header_owns_top_margin else margin_top
		else:
			self.body_page.options["marginTop"] = margin_top

		if self.footer_page:
			footer_height = self.footer_height
			footer_with_bottom_margin = footer_height + margin_bottom
			self.footer_page.options["paperHeight"] = (
				convert_uom(footer_with_bottom_margin, "px", "in", only_number=True)
				if footer_with_bottom_margin
				else 0
			)

		margin_bottom = convert_uom(margin_bottom, "px", "in", only_number=True)

		if self.footer_page:
			self.footer_page.options["marginBottom"] = margin_bottom
		else:
			self.body_page.options["marginBottom"] = margin_bottom

		body_height = options.get("page-height") - (
			header_with_spacing_top_margin + footer_with_bottom_margin
		)

		"""
		matching scale for some old formats is 1.46 #backwards-compatibility ( scale 1 is better in my opinion)
		If we face issues in custom formats then only we should enable this.
		"""

		self.body_page.options["paperHeight"] = convert_uom(body_height, "px", "in", only_number=True)

	def get_rendered_header_footer(self, content, type, head, styles, css):
		from frappe.utils.pdf import toggle_visible_pdf

		html_id = f"{type}-html"
		content = content.extract()
		toggle_visible_pdf(content)
		id_map = {"header": "pdf_header_html", "footer": "pdf_footer_html"}
		hook_func = frappe.get_hooks(id_map.get(type))
		return frappe.call(
			hook_func[-1],
			soup=self.soup,
			head=head,
			content=content,
			styles=styles,
			html_id=html_id,
			css=css,
			path="templates/print_formats/chrome_pdf_header_footer.html",
		)

	def update_header_footer_page(self):
		if not self.header_page and not self.footer_page:
			return
		total_pages = len(self.body_pdf.pages)
		# function is added to html from update_page_no.js
		if self.header_page:
			if self.is_header_dynamic:
				self.header_page.evaluate(
					f"clone_and_update('{'#header-render-container' if self.is_print_designer else '.wrapper'}', {total_pages}, {1 if self.is_print_designer else 0}, 'Header', 1);",
					await_promise=True,
				)

		if self.footer_page:
			if self.is_footer_dynamic:
				self.footer_page.evaluate(
					f"clone_and_update('{'#footer-render-container' if self.is_print_designer else '.wrapper'}', {total_pages}, {1 if self.is_print_designer else 0}, 'Footer', 1);",
					await_promise=True,
				)

	def update_header_footer_page_pd(self):
		if not self.is_print_designer:
			return
		if not self.header_page and not self.footer_page:
			return
		# function is added to html from update_page_no.js
		if self.header_page and not self.is_header_dynamic:
			self.header_page.evaluate(
				"clone_and_update('#header-render-container', 0, 1, 'Header', 0);",
				await_promise=True,
			)

		if self.footer_page and not self.is_footer_dynamic:
			self.footer_page.evaluate(
				"clone_and_update('#footer-render-container', 0, 1, 'Footer', 0);",
				await_promise=True,
			)

	def _open_header_footer_pages(self):
		self.header_page = None
		self.footer_page = None
		# open new page for header/footer if they exist.
		# It sends CDP command to the browser to open a new tab.
		if header_content := self.soup.find(id="header-html"):
			self.header_page = self.new_page("header")
			self.header_page.set_tab_url(get_host_url())

		if footer_content := self.soup.find(id="footer-html"):
			self.footer_page = self.new_page("footer")
			self.footer_page.set_tab_url(get_host_url())

		self.header_content = header_content
		self.footer_content = footer_content

	def close(self):
		self.session.disconnect()


class PageSize:
	page_sizes: ClassVar[dict[str, tuple[int, int]]] = {
		"A10": (26, 37),
		"A1": (594, 841),
		"A0": (841, 1189),
		"A3": (297, 420),
		"A2": (420, 594),
		"A5": (148, 210),
		"A4": (210, 297),
		"A7": (74, 105),
		"A6": (105, 148),
		"A9": (37, 52),
		"A8": (52, 74),
		"B10": (31, 44),
		"B1+": (720, 1020),
		"B4": (250, 353),
		"B5": (176, 250),
		"B6": (125, 176),
		"B7": (88, 125),
		"B0": (1000, 1414),
		"B1": (707, 1000),
		"B2": (500, 707),
		"B3": (353, 500),
		"B2+": (520, 720),
		"B8": (62, 88),
		"B9": (44, 62),
		"C10": (28, 40),
		"C9": (40, 57),
		"C8": (57, 81),
		"C3": (324, 458),
		"C2": (458, 648),
		"C1": (648, 917),
		"C0": (917, 1297),
		"C7": (81, 114),
		"C6": (114, 162),
		"C5": (162, 229),
		"C4": (229, 324),
		"Legal": (216, 356),
		"Junior Legal": (127, 203),
		"Letter": (216, 279),
		"Tabloid": (279, 432),
		"Ledger": (432, 279),
		"ANSI C": (432, 559),
		"ANSI A (letter)": (216, 279),
		"ANSI B (ledger & tabloid)": (279, 432),
		"ANSI E": (864, 1118),
		"ANSI D": (559, 864),
		"C5E": (163, 229),
		"Comm10E": (105, 241),
		"DLE": (110, 220),
		"Executive": (191, 254),
		"Folio": (210, 330),
	}

	@classmethod
	def get(cls, name):
		if name in cls.page_sizes:
			width, height = cls.page_sizes[name]
			return {"width": width, "height": height}
		else:
			return None  # Return None if the page size is not found
