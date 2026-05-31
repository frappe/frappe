import http
import json
import os
import uuid
from io import BytesIO
from typing import Literal
from urllib.parse import urlparse

from pypdf import PdfWriter

import frappe
from frappe import _
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.model.document import Document
from frappe.translate import print_language
from frappe.utils.jinja import render_template
from frappe.utils.pdf import get_pdf

no_cache = 1

base_template_path = "www/printview.html"
standard_format = "templates/print_formats/standard.html"

from frappe.www.printview import validate_print_permission


@frappe.whitelist()
def download_multi_pdf(
	doctype: str | dict[str, list[str]],
	name: str | list[str],
	format: str | None = None,
	no_letterhead: bool = False,
	letterhead: str | None = None,
	options: str | None = None,
):
	"""
	Calls _download_multi_pdf with the given parameters and returns the response
	"""
	if not (frappe.get_cached_value("User", frappe.session.user, "bulk_actions")):
		frappe.throw(_("You are not allowed to perform bulk actions."), frappe.PermissionError)

	return _download_multi_pdf(doctype, name, format, no_letterhead, letterhead, options)


@frappe.whitelist()
def download_multi_pdf_async(
	doctype: str | dict[str, list[str]],
	name: str | list[str],
	format: str | None = None,
	no_letterhead: bool = False,
	letterhead: str | None = None,
	options: str | None = None,
):
	"""
	Calls _download_multi_pdf with the given parameters in a background job, returns task ID
	"""
	if not frappe.get_cached_value("User", frappe.session.user, "bulk_actions"):
		frappe.throw(_("You are not allowed to perform bulk actions"), frappe.PermissionError)

	task_id = str(uuid.uuid4())
	if isinstance(doctype, dict):
		doc_count = sum([len(doctype[dt]) for dt in doctype])
	else:
		doc_count = len(json.loads(name))

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


def _download_multi_pdf(
	doctype: str | dict[str, list[str]],
	name: str | list[str],
	format: str | None = None,
	no_letterhead: bool = False,
	letterhead: str | None = None,
	options: str | None = None,
	task_id: str | None = None,
):
	"""Return a PDF compiled by concatenating multiple documents.

	The documents can be from a single DocType or multiple DocTypes.

	Note: The design may seem a little weird, but it  exists to ensure backward compatibility.
	          The correct way to use this function is to pass a dict to doctype as described below

	NEW FUNCTIONALITY
	=================
	Parameters:
	doctype (dict):
	        key (string): DocType name
	        value (list): of strings of doc names which need to be concatenated and printed
	name (string):
	        name of the pdf which is generated
	format:
	        Print Format to be used

	OLD FUNCTIONALITY - soon to be deprecated
	=========================================
	Parameters:
	doctype (string):
	        name of the DocType to which the docs belong which need to be printed
	name (string or list):
	        If string the name of the doc which needs to be printed
	        If list the list of strings of doc names which needs to be printed
	format:
	        Print Format to be used

	Returns:
	Publishes a link to the PDF to the given task ID
	"""
	filename = ""

	pdf_writer = PdfWriter()

	if isinstance(options, str):
		options = json.loads(options)

	if not isinstance(doctype, dict):
		result = json.loads(name)
		total_docs = len(result)
		filename = f"{doctype}_"

		# Concatenating pdf files
		for idx, ss in enumerate(result):
			try:
				pdf_writer = frappe.get_print(
					doctype,
					ss,
					format,
					as_pdf=True,
					output=pdf_writer,
					no_letterhead=no_letterhead,
					letterhead=letterhead,
					pdf_options=options,
				)
			except Exception:
				if task_id:
					frappe.publish_realtime(task_id=task_id, message={"message": "Failed"})

			# Publish progress
			if task_id:
				frappe.publish_progress(
					percent=(idx + 1) / total_docs * 100,
					title=_("PDF Generation in Progress"),
					description=_("{0}/{1} complete | Please leave this tab open until completion.").format(
						idx + 1, total_docs
					),
					task_id=task_id,
				)

		if task_id is None:
			frappe.local.response.filename = "{doctype}.pdf".format(
				doctype=doctype.replace(" ", "-").replace("/", "-")
			)

	else:
		total_docs = sum([len(doctype[dt]) for dt in doctype])
		count = 1
		for doctype_name in doctype:
			filename += f"{doctype_name}_"
			for doc_name in doctype[doctype_name]:
				try:
					pdf_writer = frappe.get_print(
						doctype_name,
						doc_name,
						format,
						as_pdf=True,
						output=pdf_writer,
						no_letterhead=no_letterhead,
						letterhead=letterhead,
						pdf_options=options,
					)
				except Exception:
					if task_id:
						frappe.publish_realtime(task_id=task_id, message="Failed")
					frappe.log_error(
						title="Error in Multi PDF download",
						message=f"Permission Error on doc {doc_name} of doctype {doctype_name}",
						reference_doctype=doctype_name,
						reference_name=doc_name,
					)

				count += 1

				if task_id:
					frappe.publish_progress(
						percent=count / total_docs * 100,
						title=_("PDF Generation in Progress"),
						description=_(
							"{0}/{1} complete | Please leave this tab open until completion."
						).format(count, total_docs),
						task_id=task_id,
					)
		if task_id is None:
			frappe.local.response.filename = f"{name}.pdf"

	with BytesIO() as merged_pdf:
		pdf_writer.write(merged_pdf)
		if task_id:
			_file = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": f"{filename}{task_id}.pdf",
					"content": merged_pdf.getvalue(),
					"is_private": 1,
				}
			)
			_file.save()
			frappe.publish_realtime(
				f"task_complete:{task_id}",
				message={"file_url": _file.unique_url},
				user=frappe.session.user,
			)
		else:
			frappe.local.response.filecontent = merged_pdf.getvalue()
			frappe.local.response.type = "pdf"


from frappe.deprecation_dumpster import read_multi_pdf


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
):
	if pdf_generator is None:
		pdf_generator = "wkhtmltopdf"

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


@frappe.whitelist()
def report_to_pdf(html: str, orientation: str = "Landscape"):
	make_access_log(file_type="PDF", method="PDF", page=html)
	frappe.local.response.filename = "report.pdf"
	frappe.local.response.filecontent = get_pdf(
		html,
		{
			"orientation": orientation,
			"proxy": "http://0.0.0.0:0",
			"bypass-proxy-for": urlparse(frappe.utils.get_url(allow_header_override=False)).hostname,
			"load-error-handling": "ignore",
		},
	)
	frappe.local.response.type = "pdf"


@frappe.whitelist()
def download_report_pdf(
	report_name: str,
	filters: str | dict | None = None,
	print_settings: str | dict | None = None,
	orientation: str = "Landscape",
	ignore_prepared_report: bool = False,
	custom_columns: str | list | None = None,
	is_tree: bool = False,
	parent_field: str | None = None,
	are_default_filters: bool = True,
	js_filters: str | list | None = None,
):
	html, filename = build_report_pdf_html(
		report_name,
		filters=filters,
		print_settings=print_settings,
		orientation=orientation,
		ignore_prepared_report=ignore_prepared_report,
		custom_columns=custom_columns,
		is_tree=is_tree,
		parent_field=parent_field,
		are_default_filters=are_default_filters,
		js_filters=js_filters,
	)

	make_access_log(file_type="PDF", method="PDF", page=report_name)
	frappe.local.response.filename = f"{filename}.pdf"
	frappe.local.response.filecontent = get_pdf(
		html,
		{
			"orientation": orientation,
			"proxy": "http://0.0.0.0:0",
			"bypass-proxy-for": urlparse(frappe.utils.get_url(allow_header_override=False)).hostname,
			"load-error-handling": "ignore",
		},
	)
	frappe.local.response.type = "pdf"


def build_report_pdf_html(
	report_name: str,
	filters: str | dict | None = None,
	print_settings: str | dict | None = None,
	orientation: str = "Landscape",
	ignore_prepared_report: bool = False,
	custom_columns: str | list | None = None,
	is_tree: bool = False,
	parent_field: str | None = None,
	are_default_filters: bool = True,
	js_filters: str | list | None = None,
) -> tuple[str, str]:
	"""Re-run a report on the backend and render it to print HTML.

	Returns the rendered HTML and the suggested download filename (without extension).
	"""
	from frappe.desk.query_report import run
	from frappe.model import numeric_fieldtypes
	from frappe.utils import cstr, escape_html
	from frappe.utils.formatters import format_value
	from frappe.utils.jinja_globals import is_rtl
	from frappe.www.printview import get_print_style

	if isinstance(filters, str):
		filters = json.loads(filters)

	if isinstance(print_settings, str):
		print_settings = json.loads(print_settings)

	if isinstance(js_filters, str):
		js_filters = json.loads(js_filters)

	if isinstance(custom_columns, str):
		custom_columns = json.loads(custom_columns)

	print_settings = frappe._dict(print_settings or {})

	result = run(
		report_name,
		filters,
		ignore_prepared_report=ignore_prepared_report,
		custom_columns=custom_columns or None,
		is_tree=is_tree,
		parent_field=parent_field,
		are_default_filters=are_default_filters,
		js_filters=js_filters,
	)
	report = frappe.get_doc("Report", report_name)
	columns = result.get("columns", [])
	data = result.get("result", [])

	# map against the full column list before any column filtering, else values
	# zip against the wrong fieldnames
	all_fieldnames = [col["fieldname"] for col in columns]
	for i, row in enumerate(data):
		if isinstance(row, list):
			data[i] = dict(zip(all_fieldnames, row, strict=False))

	# flag the appended total row so the template can bold it, like the client grid
	if result.get("add_total_row") and data:
		data[-1]["_is_total_row"] = True

	if print_settings.get("columns"):
		columns = [col for col in columns if col["fieldname"] in print_settings.columns]

	# Jinja autoescape is off here: escape every value except these intentionally-HTML
	# fieldtypes. Text/Small Text and Code mirror the client grid formatters below.
	html_fieldtypes = ("Text Editor", "Markdown Editor", "HTML")

	for row in data:
		for col in columns:
			fieldname = col["fieldname"]
			value = row.get(fieldname)
			fieldtype = col.get("fieldtype")
			if value is None or value == "":
				row[fieldname] = ""
			elif fieldtype == "Check":
				row[fieldname] = "✓" if value == 1 else "✗"
			elif fieldtype == "Code":
				row[fieldname] = f"<pre>{escape_html(cstr(value))}</pre>"
			elif fieldtype in ("Text", "Small Text"):
				if col.get("ignore_xss_filter"):
					row[fieldname] = format_value(value, col, row)
				else:
					row[fieldname] = escape_html(cstr(value)).replace("\n", "<br>")
			else:
				formatted = format_value(value, col, row)
				if fieldtype not in html_fieldtypes:
					formatted = escape_html(formatted)
				row[fieldname] = formatted

	letter_head = None
	if print_settings.get("with_letter_head") and print_settings.get("letter_head_name"):
		letter_head = render_letterhead_for_print(print_settings.letter_head_name)

	filters_html = ""
	if print_settings.get("include_filters") and isinstance(filters, dict):
		filter_fields = {f.fieldname: f for f in (report.filters or [])}
		for fieldname, value in filters.items():
			if not value:
				continue
			df = filter_fields.get(fieldname)
			label = escape_html(_(df.label) if df else fieldname)
			filters_html += (
				f'<div class="filter-row"><strong>{label}:</strong> {escape_html(cstr(value))}</div>'
			)

	content = frappe.get_template("templates/report/print_grid.html").render(
		{
			"title": _(report_name),
			"subtitle": filters_html or None,
			"columns": columns,
			"data": data,
			"numeric_fieldtypes": numeric_fieldtypes,
		}
	)

	print_css = get_print_style()

	html = frappe.get_template("templates/report/print_template.html").render(
		{
			"title": _(report_name),
			"content": content,
			"print_css": print_css,
			"landscape": orientation == "Landscape",
			"columns": columns,
			"lang": frappe.local.lang,
			"layout_direction": "rtl" if is_rtl() else "ltr",
			"can_use_smaller_font": report.is_standard == "Yes",
			"letter_head": letter_head,
			"repeat_header_footer": print_settings.get("repeat_header_footer"),
		}
	)

	filename = report_name.replace(" ", "-").replace("/", "-")
	if isinstance(filters, dict):
		parts = []
		length = 0
		for value in filters.values():
			length += len(str(value))
			if length > 200:
				break
			parts.append(str(value))
		if parts:
			filename += "_" + "_".join(parts)

	return html, filename


@frappe.whitelist()
def render_letterhead_for_print(letterhead: str | None = None, doc: dict | str | None = None) -> dict:
	"""Render letterhead HTML (header/footer) with Jinja for report printing."""

	if not frappe.has_permission("Letter Head", "read"):
		return {}

	if isinstance(doc, str):
		try:
			doc = json.loads(doc)
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


@frappe.whitelist()
def print_by_server(
	doctype: str,
	name: str | int,
	printer_setting: str,
	print_format: str | None = None,
	doc: Document | None = None,
	no_letterhead: bool | int = 0,
	file_path: str | None = None,
):
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
