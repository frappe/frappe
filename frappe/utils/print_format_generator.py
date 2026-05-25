# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE

from typing import ClassVar

import frappe
from frappe import _


@frappe.whitelist()
def download_pdf(doctype: str, name: str | int, print_format: str, letterhead: str | None = None):
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("print")
	generator = PrintFormatGenerator(print_format, doc, letterhead)
	pdf = generator.render_pdf()

	frappe.local.response.filename = "{name}.pdf".format(name=name.replace(" ", "-").replace("/", "-"))
	frappe.local.response.filecontent = pdf
	frappe.local.response.type = "pdf"


def get_html(doctype, name, print_format, letterhead=None):
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("print")
	generator = PrintFormatGenerator(print_format, doc, letterhead)
	return generator.get_html_preview()


class PrintFormatGenerator:
	"""Generate a PDF of a Document using Chromium-based rendering."""

	_TOP_POSITIONS: ClassVar[set[str]] = {"top_left", "top_center", "top_right"}
	_BOTTOM_POSITIONS: ClassVar[set[str]] = {"bottom_left", "bottom_center", "bottom_right"}
	_ALIGN_MAP: ClassVar[dict[str, str]] = {
		"top_left": "left",
		"top_center": "center",
		"top_right": "right",
		"bottom_left": "left",
		"bottom_center": "center",
		"bottom_right": "right",
	}

	def __init__(self, print_format, doc, letterhead=None):
		self.print_format = frappe.get_doc("Print Format", print_format)
		self.doc = doc

		if letterhead == _("No Letterhead"):
			letterhead = None
		self.letterhead = frappe.get_doc("Letter Head", letterhead) if letterhead else None

		self.build_context()
		self.layout = self.get_layout(self.print_format)
		self.context.layout = self.layout

	def build_context(self):
		self.print_settings = frappe.get_doc("Print Settings")
		page_width_map = {"A4": 210, "Letter": 216}
		page_width = page_width_map.get(self.print_settings.pdf_page_size) or 210
		body_width = page_width - self.print_format.margin_left - self.print_format.margin_right
		print_style = (
			frappe.get_doc("Print Style", self.print_settings.print_style)
			if self.print_settings.print_style
			else None
		)
		self.context = frappe._dict(
			{
				"doc": self.doc,
				"print_format": self.print_format,
				"print_settings": self.print_settings,
				"print_style": print_style,
				"letterhead": self.letterhead,
				"page_width": page_width,
				"body_width": body_width,
			}
		)

	# ----- HTML preview (browser printview) ------------------------------

	def get_html_preview(self):
		header_html, footer_html = self.get_header_footer_html()
		self.context.header = header_html
		self.context.footer = footer_html
		return self.get_main_html()

	def get_main_html(self):
		self.context.css = frappe.render_template("templates/print_format/print_format.css", self.context)
		return frappe.render_template("templates/print_format/print_format.html", self.context)

	def get_header_footer_html(self):
		header_html = footer_html = None
		if self.letterhead or self.layout.get("header"):
			header_html = frappe.render_template("templates/print_format/print_header.html", self.context)
		if self.letterhead or self.layout.get("footer"):
			footer_html = frappe.render_template("templates/print_format/print_footer.html", self.context)
		return header_html, footer_html

	# ----- PDF (Chrome) --------------------------------------------------

	def render_pdf(self):
		"""Return PDF bytes using the Chromium renderer."""
		from frappe.utils.pdf import get_chrome_pdf

		pf = self.print_format
		options = {
			"margin-top": f"{pf.margin_top}mm",
			"margin-bottom": f"{pf.margin_bottom}mm",
			"margin-left": f"{pf.margin_left}mm",
			"margin-right": f"{pf.margin_right}mm",
		}
		return get_chrome_pdf(
			print_format=pf.name,
			html=self._build_html_for_chrome(),
			options=options,
			output=None,
			pdf_generator="chrome",
		)

	def _build_html_for_chrome(self):
		"""Build the body HTML with header/footer wrapped in ``#header-html`` /
		``#footer-html`` so the Chrome PDF pipeline extracts them as overlays
		that repeat on every page.
		"""
		self.context.for_chrome = True
		self.context.header_height = 0
		self.context.footer_height = 0

		header = self._render_overlay("header")
		footer = self._render_overlay("footer")
		self.context.header = f'<div id="header-html">{header}</div>' if header else ""
		self.context.footer = f'<div id="footer-html">{footer}</div>' if footer else ""
		return self.get_main_html()

	def _render_overlay(self, kind: str) -> str | None:
		"""Render the header or footer content for the Chrome overlay.

		``kind`` is ``"header"`` or ``"footer"``. Page-number HTML is inserted
		at the top for header positions and at the bottom for footer positions
		so ``Top *`` / ``Bottom *`` actually appear where the name suggests.
		"""
		is_header = kind == "header"
		page_pos = (self.print_format.page_number or "").lower().replace(" ", "_")
		valid_positions = self._TOP_POSITIONS if is_header else self._BOTTOM_POSITIONS
		wants_page_no = page_pos in valid_positions

		if is_header:
			letterhead_html = self.letterhead and self.letterhead.content
		else:
			letterhead_html = self.letterhead and self.letterhead.footer
		layout_html = self.layout.get(kind)

		if not (letterhead_html or layout_html or wants_page_no):
			return None

		page_no_html = self._page_number_html(page_pos) if wants_page_no else None
		ctx = {"doc": self.context.doc}

		# For headers the page number goes ABOVE the letterhead, for footers BELOW.
		parts = []
		if is_header and page_no_html:
			parts.append(page_no_html)
		if letterhead_html:
			parts.append(frappe.render_template(letterhead_html, ctx))
		if layout_html:
			parts.append(frappe.render_template(layout_html, ctx))
		if not is_header and page_no_html:
			parts.append(page_no_html)
		return "\n".join(parts) or None

	def _page_number_html(self, position: str) -> str:
		align = self._ALIGN_MAP.get(position, "center")
		return (
			f'<div style="text-align:{align};font-size:10px;padding:2px 0;">'
			'<span class="page"></span>'
			f" {_('of')} "
			'<span class="topage"></span>'
			"</div>"
		)

	# ----- layout normalisation ------------------------------------------

	def get_layout(self, print_format):
		layout = frappe.parse_json(print_format.format_data)
		layout = self.set_field_renderers(layout)
		layout = self.process_margin_texts(layout)
		return layout

	def set_field_renderers(self, layout):
		renderers = {"HTML Editor": "HTML", "Markdown Editor": "Markdown"}
		for section in layout["sections"]:
			for column in section["columns"]:
				for df in column["fields"]:
					fieldtype = df["fieldtype"]
					df["renderer"] = renderers.get(fieldtype) or fieldtype.replace(" ", "")
					df["section"] = section
		return layout

	def process_margin_texts(self, layout):
		for key in (*self._TOP_POSITIONS, *self._BOTTOM_POSITIONS):
			text = layout.get("text_" + key)
			if text and "{{" in text:
				layout["text_" + key] = frappe.render_template(text, self.context)
		return layout
