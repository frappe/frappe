# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE

import warnings
from io import BytesIO

import frappe
from frappe.printing.doctype.print_format.classic_converter import uses_legacy_weasyprint
from frappe.utils import weasyprint_legacy
from frappe.utils.weasyprint_legacy import PrintFormatGenerator, import_weasyprint

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


def legacy_generator(print_format, doc, letterhead=None) -> PrintFormatGenerator:
	"""The frozen v16 WeasyPrint generator for a format still stored on WeasyPrint."""
	warn_deprecated()
	return weasyprint_legacy.PrintFormatGenerator(print_format, doc, letterhead)


def _print_format_doc(print_format):
	if isinstance(print_format, str):
		return frappe.get_doc("Print Format", print_format)
	return print_format


@frappe.whitelist()
def download_pdf(doctype: str, name: str | int, print_format: str, letterhead: str | None = None):
	from frappe.utils.print_format_generator import download_pdf as download_generator_pdf

	return download_generator_pdf(doctype, name, print_format, letterhead)


def get_html(doctype, name, print_format, letterhead=None):
	print_format = _print_format_doc(print_format)
	if uses_legacy_weasyprint(print_format):
		warn_deprecated()
		return weasyprint_legacy.get_html(doctype, name, print_format, letterhead)

	from frappe.utils.print_format_generator import get_html as get_generator_html

	return get_generator_html(doctype, name, print_format, letterhead)


def legacy_generator_from_print_context(print_format) -> PrintFormatGenerator | None:
	"""Generator for the `pdf_generator` hook, built from the print context `get_print`
	stashes; legacy callers that only set form_dict are read the same way."""
	from frappe.model.document import Document
	from frappe.utils.print_format_generator import get_print_context

	ctx = get_print_context()
	if ctx is None:
		ctx = frappe._dict(frappe.form_dict)
	if not print_format or not ctx.get("doctype") or not ctx.get("name"):
		return None
	pf = _print_format_doc(print_format)
	if not uses_legacy_weasyprint(pf):
		return None
	doc = ctx.get("doc")
	if not isinstance(doc, Document):
		doc = frappe.get_doc(ctx.doctype, ctx.name)
	return legacy_generator(pf, doc, ctx.get("letterhead"))


def get_weasyprint_pdf(print_format, html, options, output, pdf_generator=None):
	"""`pdf_generator` hook: claims builder formats whose renderer is WeasyPrint."""
	if pdf_generator != "WeasyPrint":
		return
	generator = legacy_generator_from_print_context(print_format)
	if generator is None:
		return
	pdf = generator.render_pdf(password=(options or {}).get("password"))
	if output:
		from pypdf import PdfReader

		for page in PdfReader(BytesIO(pdf)).pages:
			output.add_page(page)
		return output
	return pdf
