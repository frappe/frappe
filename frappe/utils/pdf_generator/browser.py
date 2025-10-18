from typing import ClassVar

from bs4 import BeautifulSoup

import frappe
from frappe.utils.print_utils import convert_uom, parse_float_and_unit


class Browser:
	def __init__(self, generator, print_format, html, options):
		self.is_print_designer = frappe.get_cached_value("Print Format", print_format, "print_designer")
		self.browserID = frappe.utils.random_string(10)
		generator.add_browser(self.browserID)
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
		self.body_pdf = self.body_page.generate_pdf(raw=not self.header_page and not self.footer_page)
		self.body_page.close()
		self.update_header_footer_page()

		if self.header_page:
			if not self.is_header_dynamic:
				self.header_pdf = self.header_page.get_pdf_from_stream(self.header_page.get_pdf_stream_id())
			else:
				self.header_pdf = self.header_page.generate_pdf()
			self.header_page.close()

		if self.footer_page:
			if not self.is_footer_dynamic:
				self.footer_pdf = self.footer_page.get_pdf_from_stream(self.footer_page.get_pdf_stream_id())
			else:
				self.footer_pdf = self.footer_page.generate_pdf()
			self.footer_page.close()

		self.close()

		generator.remove_browser(self.browserID)

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
		self.body_page.set_tab_url(frappe.request.host_url)
		self.body_page.wait_for_navigate()
		self.body_page.set_content(str(self.soup))

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
		# open header and footer pages
		self._open_header_footer_pages()

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

		soup: BeautifulSoup = self.soup
		options = {}
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
		options |= {style.name: style.value for style in print_format_css if style.name in attrs}
		self.options.update(options)

	def _set_default_page_size(self):
		options = self.options
		pdf_page_size = (
			options.get("page-size") or frappe.db.get_single_value("Print Settings", "pdf_page_size") or "A4"
		)

		if pdf_page_size == "Custom":
			options["page-height"] = options.get("page-height") or frappe.db.get_single_value(
				"Print Settings", "pdf_page_height"
			)
			options["page-width"] = options.get("page-width") or frappe.db.get_single_value(
				"Print Settings", "pdf_page_width"
			)
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
			"landscape": options.get("orientation", "Portrait") == "Landscape",
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

		updated_options["paperWidth"] = convert_uom(options["page-width"], "px", "in", only_number=True)

		if options.get("margin-left"):
			updated_options["marginLeft"] = convert_uom(
				self._get_converted_num(options["margin-left"]), "px", "in", only_number=True
			)

		if options.get("margin-right"):
			updated_options["marginRight"] = convert_uom(
				self._get_converted_num(options["margin-right"]), "px", "in", only_number=True
			)

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

		if self.header_page:
			header_with_top_margin = self.header_height + margin_top
			header_spacing = options.get("header-spacing", 0)
			header_with_spacing_top_margin = header_with_top_margin + header_spacing
			self.header_page.options["paperHeight"] = (
				convert_uom(header_with_spacing_top_margin, "px", "in", only_number=True)
				if header_with_spacing_top_margin
				else 0
			)

		margin_top = convert_uom(margin_top, "px", "in", only_number=True)

		if self.header_page:
			self.header_page.options["marginTop"] = margin_top
		else:
			self.body_page.options["marginTop"] = margin_top

		if self.footer_page:
			footer_height = self.footer_height
			self.footer_page.options["paperHeight"] = (
				convert_uom(footer_height, "px", "in", only_number=True) if footer_height else 0
			)
			footer_with_bottom_margin = self.footer_height + margin_bottom

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
			self.header_page.set_tab_url(frappe.request.host_url)

		if footer_content := self.soup.find(id="footer-html"):
			self.footer_page = self.new_page("footer")
			self.footer_page.set_tab_url(frappe.request.host_url)

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
		"B10": (44, 31),
		"B1+": (1020, 720),
		"B4": (353, 250),
		"B5": (250, 176),
		"B6": (176, 125),
		"B7": (125, 88),
		"B0": (1414, 1000),
		"B1": (1000, 707),
		"B2": (707, 500),
		"B3": (500, 353),
		"B2+": (720, 520),
		"B8": (88, 62),
		"B9": (62, 44),
		"C10": (40, 28),
		"C9": (57, 40),
		"C8": (81, 57),
		"C3": (458, 324),
		"C2": (648, 458),
		"C1": (917, 648),
		"C0": (1297, 917),
		"C7": (114, 81),
		"C6": (162, 114),
		"C5": (229, 162),
		"C4": (324, 229),
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
	}

	@classmethod
	def get(cls, name):
		if name in cls.page_sizes:
			width, height = cls.page_sizes[name]
			return {"width": width, "height": height}
		else:
			return None  # Return None if the page size is not found
