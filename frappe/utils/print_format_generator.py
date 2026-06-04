# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE

from typing import ClassVar

import frappe
from frappe import _


@frappe.whitelist()
def render_jinja_template(template: str, doctype: str, docname: str) -> str:
	"""Render a raw Jinja2 template string with doc context (used by the print format builder preview)."""
	doc = frappe.get_doc(doctype, docname)
	doc.check_permission("print")
	# template is rendered inside frappe's SandboxedEnvironment (Jinja2 sandbox).
	# The caller must hold the "print" permission on the document before reaching this line.
	return frappe.render_template(
		template, {"doc": doc}
	)  # nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti


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
		if self.letterhead:
			header_html = frappe.render_template("templates/print_format/print_header.html", self.context)
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
		"""Build the body HTML for the Chrome PDF pipeline.

		When ``repeat_header_footer`` is enabled (default), letterhead and
		layout header/footer are placed in ``#header-html`` / ``#footer-html``
		overlay divs so they repeat on every PDF page.

		When ``repeat_header_footer`` is disabled:
		  - Letterhead + layout header/footer → rendered inline in the body
		    (appear on page 1 / last page only via ``chrome_layout_header/footer``).
		  - Page numbers → still placed in a minimal ``#header-html`` / ``#footer-html``
		    overlay so they continue to repeat on every page if the user enabled them.
		"""
		self.context.for_chrome = True
		self.context.header_height = 0
		self.context.footer_height = 0

		repeat = self.print_settings.repeat_header_footer

		if repeat:
			header = self._render_overlay("header")
			footer = self._render_overlay("footer")
			self.context.header = f'<div id="header-html">{header}</div>' if header else ""
			self.context.footer = f'<div id="footer-html">{footer}</div>' if footer else ""
			self.context.chrome_layout_header = ""
			self.context.chrome_layout_footer = ""
		else:
			# Letterhead + layout content → inline (once only, no repeat).
			self.context.chrome_layout_header = self._render_overlay("header", with_page_no=False) or ""
			self.context.chrome_layout_footer = self._render_overlay("footer", with_page_no=False) or ""
			# Page numbers → minimal overlay so they still repeat on every page.
			page_no_header = self._render_page_no_overlay("header")
			page_no_footer = self._render_page_no_overlay("footer")
			self.context.header = f'<div id="header-html">{page_no_header}</div>' if page_no_header else ""
			self.context.footer = f'<div id="footer-html">{page_no_footer}</div>' if page_no_footer else ""

		return self.get_main_html()

	def _render_page_no_overlay(self, kind: str) -> str | None:
		"""Return only the page-number HTML for kind ('header'/'footer'), or None."""
		is_header = kind == "header"
		page_pos = (self.print_format.page_number or "").lower().replace(" ", "_")
		valid_positions = self._TOP_POSITIONS if is_header else self._BOTTOM_POSITIONS
		if page_pos not in valid_positions:
			return None
		return self._page_number_html(page_pos)

	def _render_overlay(self, kind: str, with_page_no: bool = True) -> str | None:
		"""Render letterhead, layout.header/footer, and page number for the Chrome overlay.

		All three are included so they repeat on every PDF page.  Height measurement
		is reliable because ``chrome_pdf_header_footer.html`` applies ``overflow: hidden``
		to ``.wrapper``, creating a BFC that contains floated letterhead children.
		"""
		is_header = kind == "header"
		page_pos = (self.print_format.page_number or "").lower().replace(" ", "_")
		valid_positions = self._TOP_POSITIONS if is_header else self._BOTTOM_POSITIONS
		wants_page_no = with_page_no and page_pos in valid_positions

		if is_header:
			letterhead_html = self.letterhead and self.letterhead.content
			layout_template = self.layout.get("header") if self.layout else None
		else:
			letterhead_html = self.letterhead and self.letterhead.footer
			layout_template = self.layout.get("footer") if self.layout else None

		if not (letterhead_html or wants_page_no or layout_template):
			return None

		page_no_html = self._page_number_html(page_pos) if wants_page_no else None
		ctx = {"doc": self.context.doc}

		parts = []
		if is_header and page_no_html:
			parts.append(page_no_html)
		if letterhead_html:
			parts.append(frappe.render_template(letterhead_html, ctx))
		if layout_template:
			if isinstance(layout_template, str):
				# layout_template is persisted header/footer HTML from the stored Print Format document.
				zone_html = frappe.render_template(
					layout_template, ctx
				)  # nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
			else:
				# Section object — render using the same logic as print_format.html
				zone_html = self._render_zone_section(layout_template, ctx["doc"])
			if zone_html:
				parts.append('<div class="document-header-content">' + zone_html + "</div>")
		if not is_header and page_no_html:
			parts.append(page_no_html)
		return "\n".join(parts) or None

	_ZONE_SECTION_TEMPLATE = """\
{%- set ns = namespace(has_fields=false) -%}
{%- for col in section.columns -%}{%- for df in col.get('fields', []) -%}{%- set ns.has_fields = true -%}{%- endfor -%}{%- endfor -%}
{%- if ns.has_fields -%}
{%- set col_gap = (section.gap if section.gap is defined and section.gap is not none else 20)|string + 'px' -%}
{%- set _lc = 'label-uppercase' if section.get('label_case') == 'uppercase' else '' -%}
<div class="section {{ _lc }} section-columns row" style="gap:{{ col_gap }}">
{%- for column in section.columns %}
<div class="column col">
{%- for df in column.get('fields', []) -%}
{%- if df.fieldtype == 'HTML' and df.html -%}
<div class="custom-html">{{ frappe.render_template(df.html, {'doc': doc}) }}</div>
{%- elif df.fieldtype == 'Spacer' -%}
<div style="height:12px"></div>
{%- elif df.fieldtype == 'Divider' -%}
<hr style="border-top:1px solid #e5e7eb;margin:4px 0"/>
{%- else -%}
{%- set _raw = doc.get(df.fieldname) -%}
{%- if _raw is not none and _raw != '' -%}
<div class="field-render">
{%- if df.show_label != 'hide' %}<div class="label">{{ _(df.label or df.fieldname) }}</div>{%- endif -%}
<div class="value">{{ doc.get_formatted(df.fieldname) }}</div>
</div>
{%- endif -%}
{%- endif -%}
{%- endfor -%}
</div>
{%- endfor %}
</div>
{%- endif -%}
"""

	def _render_zone_section(self, section: dict, doc) -> str:
		"""Render a header/footer zone section dict to HTML for the Chrome overlay."""
		# _ZONE_SECTION_TEMPLATE is a hardcoded class-level string constant, not user input.
		return frappe.render_template(
			self._ZONE_SECTION_TEMPLATE, {"section": section, "doc": doc}
		)  # nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti

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

		# Also process header/footer zones if they are section objects
		for zone_key in ("header", "footer"):
			zone = layout.get(zone_key)
			if isinstance(zone, dict) and "columns" in zone:
				for column in zone.get("columns", []):
					for df in column.get("fields", []):
						fieldtype = df.get("fieldtype", "Data")
						df["renderer"] = renderers.get(fieldtype) or fieldtype.replace(" ", "")
						df["section"] = zone

		return layout

	def process_margin_texts(self, layout):
		for key in (*self._TOP_POSITIONS, *self._BOTTOM_POSITIONS):
			text = layout.get("text_" + key)
			if text and "{{" in text:
				layout["text_" + key] = frappe.render_template(text, self.context)
		return layout
