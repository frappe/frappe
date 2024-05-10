# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE

import click

import frappe
from frappe import _


@frappe.whitelist()
def download_pdf(doctype, name, print_format, letterhead=None):
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
	"""
	Generate a PDF of a Document, with repeatable header and footer if letterhead is provided.

	This generator draws its inspiration and, also a bit of its implementation, from this
	discussion in the library github issues: https://github.com/Kozea/WeasyPrint/issues/92
	"""

	def __init__(self, print_format, doc, letterhead=None):
		"""
		Parameters
		----------
		print_format: str
		        Name of the Print Format
		doc: str
		        Document to print
		letterhead: str
		        Letter Head to apply (optional)
		"""
		self.base_url = frappe.utils.get_url()
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
		context = frappe._dict(
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
		self.context = context

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
		if self.letterhead:
			footer_html = frappe.render_template("templates/print_format/print_footer.html", self.context)
		return header_html, footer_html

	def render_pdf(self):
		"""Return a bytes sequence of the rendered PDF."""
		HTML, CSS = import_weasyprint()

		self._make_header_footer()

		self.context.update({"header_height": self.header_height, "footer_height": self.footer_height})
		main_html = self.get_main_html()

		html = HTML(string=main_html, base_url=self.base_url)
		main_doc = html.render()

		if self.header_html or self.footer_html:
			self._apply_overlay_on_main(main_doc, self.header_body, self.footer_body)
		return main_doc.write_pdf()

	def _compute_overlay_element(self, element: str):
		"""
		Parameters
		----------
		element: str
		        Either 'header' or 'footer'

		Returns
		-------
		element_body: BlockBox
		        A Weasyprint pre-rendered representation of an html element
		element_height: float
		        The height of this element, which will be then translated in a html height
		"""
		HTML, CSS = import_weasyprint()

		html = HTML(
			string=getattr(self, f"{element}_html"),
			base_url=self.base_url,
		)
		element_doc = html.render(stylesheets=[CSS(string="@page {size: A4 portrait; margin: 0;}")])
		element_page = element_doc.pages[0]
		element_body = PrintFormatGenerator.get_element(element_page._page_box.all_children(), "body")
		element_body = element_body.copy_with_children(element_body.all_children())
		element_html = PrintFormatGenerator.get_element(element_page._page_box.all_children(), element)

		if element == "header":
			element_height = element_html.height
		if element == "footer":
			element_height = element_page.height - element_html.position_y

		return element_body, element_height

	def _apply_overlay_on_main(self, main_doc, header_body=None, footer_body=None):
		"""
		Insert the header and the footer in the main document.

		Parameters
		----------
		main_doc: Document
		        The top level representation for a PDF page in Weasyprint.
		header_body: BlockBox
		        A representation for an html element in Weasyprint.
		footer_body: BlockBox
		        A representation for an html element in Weasyprint.
		"""
		for page in main_doc.pages:
			page_body = PrintFormatGenerator.get_element(page._page_box.all_children(), "body")

			if header_body:
				page_body.children += header_body.all_children()
			if footer_body:
				page_body.children += footer_body.all_children()

	def _make_header_footer(self):
		self.header_html, self.footer_html = self.get_header_footer_html()

		if self.header_html:
			header_body, header_height = self._compute_overlay_element("header")
		else:
			header_body, header_height = None, 0
		if self.footer_html:
			footer_body, footer_height = self._compute_overlay_element("footer")
		else:
			footer_body, footer_height = None, 0

		self.header_body = header_body
		self.header_height = header_height
		self.footer_body = footer_body
		self.footer_height = footer_height

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
					renderer_name = fieldtype.replace(" ", "")
					df["renderer"] = renderers.get(fieldtype) or renderer_name
					df["section"] = section
		return layout

	def process_margin_texts(self, layout):
		margin_texts = [
			"top_left",
			"top_center",
			"top_right",
			"bottom_left",
			"bottom_center",
			"bottom_right",
		]
		for key in margin_texts:
			text = layout.get("text_" + key)
			if text and "{{" in text:
				layout["text_" + key] = frappe.render_template(text, self.context)

		return layout

	@staticmethod
	def get_element(boxes, element):
		"""
		Given a set of boxes representing the elements of a PDF page in a DOM-like way, find the
		box which is named `element`.

		Look at the notes of the class for more details on Weasyprint insides.
		"""
		for box in boxes:
			if box.element_tag == element:
				return box
			return PrintFormatGenerator.get_element(box.all_children(), element)


def import_weasyprint():
	try:
		from weasyprint import CSS, HTML

		return HTML, CSS
	except OSError:
		message = "\n".join(
			[
				"WeasyPrint depdends on additional system dependencies.",
				"Follow instructions specific to your operating system:",
				"https://doc.courtbouillon.org/weasyprint/stable/first_steps.html",
			]
		)
		click.secho(message, fg="yellow")
		frappe.throw(message)
