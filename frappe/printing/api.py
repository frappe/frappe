# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Public printing API — render print formats and generate PDFs.

Endpoints were consolidated from `frappe.utils.print_format` and
`frappe.www.printview`; the old dotted paths keep working via aliases in
the original modules.
"""

import http
import os
import uuid
from typing import Literal

from pypdf import PdfWriter

import frappe
from frappe import _
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.model.document import Document
from frappe.public_api import public
from frappe.translate import print_language
from frappe.utils.jinja import render_template
from frappe.utils.pdf import get_pdf
from frappe.utils.print_format import _download_multi_pdf, _pdf_bypass_proxy_hosts
from frappe.www.printview import (
	get_print_format_doc,
	get_print_style,
	get_rendered_template,
	set_link_titles,
	validate_print_for_docstatus,
	validate_print_permission,
)


@public(group="Printing")
@frappe.whitelist()
def download_multi_pdf(
	doctype: str | dict[str, list[str]],
	name: str | list[str],
	format: str | None = None,
	no_letterhead: bool = False,
	letterhead: str | None = None,
	options: str | None = None,
) -> None:
	"""Download a merged PDF of multiple documents.

	:param doctype: DocType, or a dict mapping each doctype to its document names
	:param name: names of the documents, when `doctype` is a single DocType
	:param format: name of the Print Format to use
	:param no_letterhead: render without a letterhead
	:param letterhead: name of the Letter Head to use
	:param options: PDF options as JSON
	"""
	if not (frappe.get_cached_value("User", frappe.session.user, "bulk_actions")):
		frappe.throw(_("You are not allowed to perform bulk actions."), frappe.PermissionError)

	return _download_multi_pdf(doctype, name, format, no_letterhead, letterhead, options)


@public(group="Printing")
@frappe.whitelist()
def download_multi_pdf_async(
	doctype: str | dict[str, list[str]],
	name: str | list[str],
	format: str | None = None,
	no_letterhead: bool = False,
	letterhead: str | None = None,
	options: str | None = None,
) -> dict[str, str]:
	"""Generate a merged PDF of multiple documents in a background job.

	:param doctype: DocType, or a dict mapping each doctype to its document names
	:param name: names of the documents, when `doctype` is a single DocType
	:param format: name of the Print Format to use
	:param no_letterhead: render without a letterhead
	:param letterhead: name of the Letter Head to use
	:param options: PDF options as JSON
	:return: Dict with the `task_id` to track the job by.
	"""
	if not frappe.get_cached_value("User", frappe.session.user, "bulk_actions"):
		frappe.throw(_("You are not allowed to perform bulk actions"), frappe.PermissionError)

	task_id = str(uuid.uuid4())
	if isinstance(doctype, dict):
		doc_count = sum([len(doctype[dt]) for dt in doctype])
	else:
		doc_count = len(frappe.parse_json(name))

	frappe.enqueue(
		_download_multi_pdf,
		doctype=doctype,
		name=name,
		task_id=task_id,
		format=format,
		no_letterhead=no_letterhead,
		letterhead=letterhead,
		options=options,
		queue="long" if doc_count > 20 else "short",
		at_front_when_starved=True,
	)
	frappe.local.response["http_status_code"] = http.HTTPStatus.CREATED
	return {"task_id": task_id}


@public(group="Printing")
@frappe.whitelist(allow_guest=True)
def download_pdf(
	doctype: str,
	name: str,
	format: str | None = None,
	doc: Document | None = None,
	no_letterhead: bool | int = 0,
	language: str | None = None,
	letterhead: str | None = None,
	pdf_generator: Literal["wkhtmltopdf", "chrome"] | None = None,
) -> None:
	"""Download a document's print format as PDF.

	:param doctype: DocType of the document
	:param name: name of the document
	:param format: name of the Print Format to use
	:param doc: already-loaded document, to skip fetching it again
	:param no_letterhead: render without a letterhead
	:param language: render in this language
	:param letterhead: name of the Letter Head to use
	:param pdf_generator: PDF engine to render with
	"""
	doc = doc or frappe.get_doc(doctype, name)
	validate_print_permission(doc)

	with print_language(language):
		pdf_file = frappe.get_print(
			doctype,
			name,
			format,
			doc=doc,
			as_pdf=True,
			letterhead=letterhead,
			no_letterhead=no_letterhead,
			pdf_generator=pdf_generator,
		)

	frappe.local.response.filename = "{name}.pdf".format(name=name.replace(" ", "-").replace("/", "-"))
	frappe.local.response.filecontent = pdf_file
	frappe.local.response.type = "pdf"


@public(group="Printing")
@frappe.whitelist()
def report_to_pdf(html: str, orientation: str = "Landscape") -> None:
	"""Download the given report HTML as PDF.

	:param html: rendered report HTML
	:param orientation: page orientation, Landscape or Portrait
	"""
	make_access_log(file_type="PDF", method="PDF", page=html)
	frappe.local.response.filename = "report.pdf"
	frappe.local.response.filecontent = get_pdf(
		html,
		{
			"orientation": orientation,
			"proxy": "http://0.0.0.0:0",
			"bypass-proxy-for": _pdf_bypass_proxy_hosts(),
			"load-error-handling": "ignore",
		},
	)
	frappe.local.response.type = "pdf"


@public(group="Printing")
@frappe.whitelist()
def render_letterhead_for_print(letterhead: str | None = None, doc: dict | str | None = None) -> dict:
	"""Render letterhead HTML (header/footer) with Jinja for report printing."""

	if not frappe.has_permission("Letter Head", "read"):
		return {}

	if isinstance(doc, str):
		try:
			doc = frappe.parse_json(doc)
		except Exception:
			doc = {}

	letter_head = frappe._dict(
		frappe.db.get_value(
			"Letter Head",
			letterhead or {"is_default": 1},
			["content", "footer", "header_script", "footer_script", "custom_css"],
			as_dict=True,
		)
		or {}
	)

	context_doc = frappe._dict(doc or {})
	rendered = {}

	if letter_head.content:
		header = render_template(letter_head.content, {"doc": context_doc})
		if letter_head.custom_css:
			header += f"\n<style>\n{letter_head.custom_css}\n</style>\n"
		rendered["header"] = header
		if letter_head.header_script:
			header += f"\n<script>\n{letter_head.header_script}\n</script>\n"

	if letter_head.footer:
		footer = render_template(letter_head.footer, {"doc": context_doc})
		if letter_head.footer_script:
			footer += f"\n<script>\n{letter_head.footer_script}\n</script>\n"
		rendered["footer"] = footer

	return rendered


@public(group="Printing")
@frappe.whitelist()
def print_by_server(
	doctype: str,
	name: str | int,
	printer_setting: str,
	print_format: str | None = None,
	doc: Document | None = None,
	no_letterhead: bool | int = 0,
	file_path: str | None = None,
) -> None:
	"""Print a document on a network (CUPS) printer.

	:param doctype: DocType of the document
	:param name: name of the document
	:param printer_setting: name of the Network Printer Settings to print with
	:param print_format: name of the Print Format to use
	:param doc: already-loaded document, to skip fetching it again
	:param no_letterhead: render without a letterhead
	:param file_path: where to write the intermediate PDF file
	"""
	print_settings = frappe.get_doc("Network Printer Settings", printer_setting)
	try:
		import cups
	except ImportError:
		frappe.throw(_("You need to install pycups to use this feature!"))

	try:
		cups.setServer(print_settings.server_ip)
		cups.setPort(print_settings.port)
		conn = cups.Connection()
		output = PdfWriter()
		output = frappe.get_print(
			doctype, name, print_format, doc=doc, no_letterhead=no_letterhead, as_pdf=True, output=output
		)
		if not file_path:
			file_path = os.path.join("/", "tmp", f"frappe-pdf-{frappe.generate_hash()}.pdf")
		output.write(open(file_path, "wb"))
		conn.printFile(print_settings.printer_name, file_path, name, {})
	except OSError as e:
		if (
			"ContentNotFoundError" in e.message
			or "ContentOperationNotPermittedError" in e.message
			or "UnknownContentError" in e.message
			or "RemoteHostClosedError" in e.message
		):
			frappe.throw(_("PDF generation failed"))
	except cups.IPPError:
		frappe.throw(_("Printing failed"))


@public(group="Printing")
@frappe.whitelist()
def get_html_and_style(
	doc: str | dict,
	name: str | None = None,
	print_format: str | None = None,
	no_letterhead: bool | None = None,
	letterhead: str | None = None,
	trigger_print: bool = False,
	style: str | None = None,
	settings: str | dict | None = None,
) -> dict[str, str | None]:
	"""Return `html` and `style` of print format, used in PDF etc."""

	if isinstance(doc, str) and isinstance(name, str):
		document = frappe.get_lazy_doc(doc, name, check_permission=True)
	else:
		document = frappe.get_doc(frappe.parse_json(doc), check_permission=True)

	print_format = get_print_format_doc(print_format, meta=document.meta)
	set_link_titles(document)

	from frappe.printing.doctype.print_format.classic_converter import (
		get_default_print_format,
		uses_beta_renderer,
	)

	if print_format is None:
		print_format = get_default_print_format(document.doctype)

	if uses_beta_renderer(print_format):
		from frappe.utils.print_format_generator import PrintFormatGenerator

		validate_print_permission(document)
		validate_print_for_docstatus(document)
		generator = PrintFormatGenerator(
			print_format,
			document,
			None if no_letterhead else letterhead,
			settings=frappe.parse_json(settings),
		)
		html = generator.get_html_preview()
	else:
		try:
			html = get_rendered_template(
				doc=document,
				print_format=print_format,
				meta=document.meta,
				no_letterhead=no_letterhead,
				letterhead=letterhead,
				trigger_print=trigger_print,
				settings=frappe.parse_json(settings),
			)
		except frappe.TemplateNotFoundError:
			frappe.clear_last_message()
			html = None

	return {"html": html, "style": get_print_style(style=style, print_format=print_format)}


@public(group="Printing")
@frappe.whitelist()
def get_rendered_raw_commands(
	doc: str | dict, name: str | None = None, print_format: str | None = None
) -> dict:
	"""Return Rendered Raw Commands of print format, used to send directly to printer."""

	if isinstance(doc, str) and isinstance(name, str):
		document = frappe.get_lazy_doc(doc, name, check_permission=True)
	else:
		document = frappe.get_doc(frappe.parse_json(doc), check_permission=True)

	print_format = get_print_format_doc(print_format, meta=document.meta)

	if not print_format or (print_format and not print_format.raw_printing):
		frappe.throw(
			_("{0} is not a raw printing format.").format(print_format), frappe.TemplateNotFoundError
		)

	return {
		"raw_commands": get_rendered_template(doc=document, print_format=print_format, meta=document.meta)
	}
