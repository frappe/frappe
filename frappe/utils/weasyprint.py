# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE

import warnings
from io import BytesIO

import click

import frappe
from frappe.utils.print_format_generator import PrintFormatGenerator

DEPRECATION_MESSAGE = (
	"WeasyPrint PDF rendering is deprecated and will be removed in version 17. "
	"Switch the print format to Chrome."
)

_deprecation_warned = False


def warn_deprecated():
	global _deprecation_warned
	if _deprecation_warned:
		return
	_deprecation_warned = True
	warnings.warn(DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=3)


@frappe.whitelist()
def download_pdf(doctype: str, name: str | int, print_format: str, letterhead: str | None = None):
	from frappe.utils.print_format_generator import download_pdf as download_generator_pdf

	return download_generator_pdf(doctype, name, print_format, letterhead)


def get_html(doctype, name, print_format, letterhead=None):
	from frappe.utils.print_format_generator import get_html as get_generator_html

	return get_generator_html(doctype, name, print_format, letterhead)


def get_weasyprint_pdf(print_format, html, options, output, pdf_generator=None):
	"""`pdf_generator` hook: claims builder formats whose renderer is WeasyPrint."""
	if pdf_generator != "WeasyPrint":
		return
	from frappe.utils.print_format_generator import generator_from_print_context

	generator = generator_from_print_context(print_format)
	if generator is None:
		return
	pdf = render_weasyprint(generator, password=(options or {}).get("password"))
	if output:
		from pypdf import PdfReader

		for page in PdfReader(BytesIO(pdf)).pages:
			output.add_page(page)
		return output
	return pdf


def render_weasyprint(generator: PrintFormatGenerator, password: str | None = None) -> bytes:
	"""Render the generator's document through WeasyPrint: header and footer are
	measured on their own, the page box keeps room for them and each page gets
	them overlaid (https://github.com/Kozea/WeasyPrint/issues/92)."""
	warn_deprecated()
	HTML, CSS = import_weasyprint()

	base_url = frappe.utils.get_url()
	width, height = generator.page_size_mm()
	page_css = CSS(string=f"@page {{ size: {width}mm {height}mm; margin: 0; }}")

	header_html = generator.weasyprint_zone_html("header")
	footer_html = generator.weasyprint_zone_html("footer")
	header_body, header_height = _measure_overlay(HTML, header_html, "header", base_url, page_css)
	footer_body, footer_height = _measure_overlay(HTML, footer_html, "footer", base_url, page_css)

	main_html = generator.build_html_for_weasyprint(header_height=header_height, footer_height=footer_height)
	main_doc = HTML(string=main_html, base_url=base_url).render()
	if header_body or footer_body:
		_apply_overlay_on_main(main_doc, header_body, footer_body)
	pdf = main_doc.write_pdf()
	if password:
		pdf = _encrypt(pdf, password)
	return pdf


def _encrypt(pdf: bytes, password: str) -> bytes:
	from pypdf import PdfReader, PdfWriter

	writer = PdfWriter(clone_from=PdfReader(BytesIO(pdf)))
	writer.encrypt(user_password=password)
	out = BytesIO()
	writer.write(out)
	return out.getvalue()


def _measure_overlay(HTML, element_html: str, element: str, base_url: str, page_css):
	"""Pre-render a header/footer block on its own page and return its body box and height."""
	if not element_html:
		return None, 0
	element_doc = HTML(string=element_html, base_url=base_url).render(stylesheets=[page_css])
	element_page = element_doc.pages[0]
	element_body = get_element(element_page._page_box.all_children(), "body")
	element_body = element_body.copy_with_children(element_body.all_children())
	element_box = get_element(element_page._page_box.all_children(), element)
	if element == "header":
		element_height = element_box.height
	else:
		element_height = element_page.height - element_box.position_y
	return element_body, element_height


def _apply_overlay_on_main(main_doc, header_body=None, footer_body=None):
	for page in main_doc.pages:
		page_body = get_element(page._page_box.all_children(), "body")
		if header_body:
			page_body.children += header_body.all_children()
		if footer_body:
			page_body.children += footer_body.all_children()


def get_element(boxes, element):
	"""Find the first box named `element` in a WeasyPrint page box tree."""
	for box in boxes:
		if box.element_tag == element:
			return box
		found = get_element(box.all_children(), element)
		if found is not None:
			return found
	return None


def import_weasyprint():
	try:
		from weasyprint import CSS, HTML

		return HTML, CSS
	except OSError:
		message = "\n".join(
			[
				"WeasyPrint depends on additional system dependencies.",
				"Follow instructions specific to your operating system:",
				"https://doc.courtbouillon.org/weasyprint/stable/first_steps.html",
			]
		)
		click.secho(message, fg="yellow")
		frappe.throw(message)
