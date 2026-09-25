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

MULTI_PDF_ASYNC_RATE_LIMIT = 10
MULTI_PDF_ASYNC_RATE_WINDOW = 60


def get_max_bulk_print_docs() -> int:
	"""Return the maximum documents allowed in one bulk PDF export."""
	return (
		frappe.cint(frappe.db.get_single_value("Print Settings", "max_bulk_print_docs"))
		or frappe.cint(frappe.conf.get("max_bulk_print_docs"))
		or 100
	)


def get_max_concurrent_bulk_exports() -> int:
	"""Return the maximum concurrent bulk PDF exports allowed per user."""
	return (
		frappe.cint(frappe.db.get_single_value("Print Settings", "max_concurrent_bulk_exports"))
		or frappe.cint(frappe.conf.get("max_concurrent_bulk_exports"))
		or 5
	)


def _enforce_multi_pdf_async_rate_limit():
	cache_key = frappe.cache.make_key(f"rl:multi_pdf_async:{frappe.session.user}")
	# nosemgrep: frappe-semgrep-rules.rules.frappe-cache-breaks-multitenancy
	frappe.cache.set(cache_key, 0, nx=True, ex=MULTI_PDF_ASYNC_RATE_WINDOW)

	if frappe.cache.incrby(cache_key, 1) > MULTI_PDF_ASYNC_RATE_LIMIT:
		frappe.throw(
			_("You hit the rate limit because of too many requests. Please try after sometime."),
			frappe.RateLimitExceededError,
		)


def _get_multi_pdf_doc_count(doctype: str | dict[str, list[str]], name: str | list[str]) -> int:
	if isinstance(doctype, dict):
		return sum([len(doctype[dt]) for dt in doctype])
	return len(frappe.parse_json(name))


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
	max_docs = get_max_bulk_print_docs()
	if _get_multi_pdf_doc_count(doctype, name) > max_docs:
		frappe.throw(_("Cannot generate PDF for more than {0} documents at a time").format(max_docs))

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
	_enforce_multi_pdf_async_rate_limit()

	doc_count = _get_multi_pdf_doc_count(doctype, name)
	max_docs = get_max_bulk_print_docs()
	if doc_count > max_docs:
		frappe.throw(_("Cannot generate PDF for more than {0} documents at a time").format(max_docs))

	task_id = str(uuid.uuid4())

	job = None
	for slot in range(get_max_concurrent_bulk_exports()):
		job = frappe.enqueue(
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
			job_id=f"multi_pdf_async:{frappe.session.user}:{slot}",
			deduplicate=True,
		)
		if job is not None:
			break

	if job is None:
		frappe.throw(
			_(
				"You already have the maximum number of bulk PDF exports in progress. Please wait for one to finish."
			),
			frappe.RateLimitExceededError,
		)

	frappe.local.response["http_status_code"] = http.HTTPStatus.CREATED
	return {"task_id": task_id}


def page_settings(pdf_options) -> dict:
	pdf_options = pdf_options or {}
	settings = {}
	for option, setting in (
		("page-size", "pdf_page_size"),
		("page-height", "pdf_page_height"),
		("page-width", "pdf_page_width"),
	):
		if pdf_options.get(option):
			settings[setting] = pdf_options[option]
	if "pdf_page_height" in settings and "pdf_page_size" not in settings:
		settings["pdf_page_size"] = "Custom"
	return settings


def classic_page_options(pdf_options) -> dict:
	pdf_options = dict(pdf_options or {})
	for option in ("page-height", "page-width"):
		if isinstance(pdf_options.get(option), int | float):
			pdf_options[option] = f"{pdf_options[option]}mm"
			pdf_options["page-size"] = "Custom"
	return pdf_options


def publish_failure(task_id, error):
	if task_id:
		frappe.publish_realtime(
			f"task_complete:{task_id}",
			message={
				"error": str(error) or _("You are not permitted to print one of the selected documents")
			},
			user=frappe.session.user,
		)


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

	if (options or {}).get("password") and format:
		if frappe.db.get_value("Print Format", format, "pdf_generator") == "Typst":
			frappe.throw(_("PDF encryption is not supported by the Typst renderer"))

	format_language = format and frappe.db.get_value("Print Format", format, "default_print_language")

	def print_into_writer(print_doctype, print_name):
		with print_language(format_language):
			return _print_into_writer(print_doctype, print_name)

	def _print_into_writer(print_doctype, print_name):
		from frappe.utils.print_utils import _print_format_doc_or_none, renders_through_generator

		pf_doc = _print_format_doc_or_none(format)
		if not renders_through_generator(pf_doc):
			return frappe.get_print(
				print_doctype,
				print_name,
				format,
				as_pdf=True,
				output=pdf_writer,
				no_letterhead=no_letterhead,
				letterhead=letterhead,
				pdf_options=classic_page_options(options),
			)

		from pypdf import PdfReader

		from frappe.printing.doctype.print_format.classic_converter import uses_legacy_weasyprint
		from frappe.utils.print_format_generator import PrintFormatGenerator
		from frappe.www.printview import set_link_titles, validate_print

		doc = frappe.get_doc(print_doctype, print_name)
		validate_print(doc)
		if uses_legacy_weasyprint(pf_doc):
			from frappe.utils.weasyprint import legacy_generator

			pdf = legacy_generator(pf_doc, doc, letterhead).render_pdf()
		else:
			set_link_titles(doc)
			generator = PrintFormatGenerator(
				pf_doc, doc, letterhead, no_letterhead=no_letterhead, settings=page_settings(options)
			)
			pdf = generator.render_pdf()
		for page in PdfReader(BytesIO(pdf)).pages:
			pdf_writer.add_page(page)
		return pdf_writer

	if not isinstance(doctype, dict):
		result = json.loads(name)
		total_docs = len(result)
		filename = f"{doctype}_"

		# Concatenating pdf files
		for idx, ss in enumerate(result):
			try:
				pdf_writer = print_into_writer(doctype, ss)
			except frappe.PermissionError as e:
				publish_failure(task_id, e)
				raise
			except Exception:
				frappe.log_error(
					title="Error in Multi PDF download",
					reference_doctype=doctype,
					reference_name=ss,
				)
				if task_id:
					frappe.publish_realtime(
						task_id=task_id, message={"message": "Failed"}, user=frappe.session.user
					)

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
					pdf_writer = print_into_writer(doctype_name, doc_name)
				except frappe.PermissionError as e:
					publish_failure(task_id, e)
					raise
				except Exception:
					if task_id:
						frappe.publish_realtime(task_id=task_id, message="Failed", user=frappe.session.user)
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

	if password := (options or {}).get("password"):
		pdf_writer.encrypt(password)

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


# nosemgrep: frappe-semgrep-rules.rules.security.guest-whitelisted-method
@frappe.whitelist(allow_guest=True)
@frappe.concurrent_limit()
def download_pdf(
	doctype: str,
	name: str,
	format: str | None = None,
	doc: Document | None = None,
	no_letterhead: bool | int = 0,
	language: str | None = None,
	letterhead: str | None = None,
	pdf_generator: Literal["wkhtmltopdf", "chrome", "Typst", "WeasyPrint"] | None = None,
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
@frappe.concurrent_limit()
def report_to_pdf(html: str, orientation: str = "Landscape"):
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
		smart_shrinking=True,
	)
	frappe.local.response.type = "pdf"


def _pdf_bypass_proxy_hosts() -> list[str]:
	"""Hosts wkhtmltopdf is allowed to fetch from while rendering a report PDF.

	The report HTML is built client-side and posted back, so its asset URLs are
	absolute against whichever domain the user is browsing. wkhtmltopdf is pinned
	to a dead proxy and only bypasses it for these hosts, so a site reached via a
	secondary domain would otherwise fail every asset fetch with UnknownNetworkError.

	Always allows the canonical host. Additional hosts (e.g. a site's alternate
	domains) can be allowed via the `domains` site config key. The bypass list is
	limited to these, so genuinely external resources stay blocked.
	"""
	hosts = {_hostname(frappe.utils.get_url(allow_header_override=False))}
	hosts.update(_hostname(domain) for domain in (frappe.conf.domains or []))
	hosts.discard(None)
	return sorted(hosts)


def _hostname(value: str) -> str | None:
	"""Bare hostname for a `--bypass-proxy-for` entry.

	wkhtmltopdf wants a bare host, but config values may arrive as a full URL,
	with a scheme, or with a port (e.g. "https://a.com", "a.com:443"). urlparse
	only finds the host in the netloc, so give bare values one before parsing —
	otherwise an un-normalized entry silently fails the bypass for that domain.
	"""
	if "://" not in value:
		value = "//" + value
	return urlparse(value).hostname


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
			["content", "footer", "header_script", "footer_script"],
			as_dict=True,
		)
		or {}
	)

	context_doc = frappe._dict(doc or {})
	rendered = {}

	if letter_head.content:
		header = render_template(letter_head.content, {"doc": context_doc})
		if letter_head.header_script:
			header += f"\n<script>\n{letter_head.header_script}\n</script>\n"
		rendered["header"] = header

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
