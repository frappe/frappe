import http
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

from frappe.www.printview import validate_print_permission


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

	options = frappe.parse_json(options)

	if not isinstance(doctype, dict):
		result = frappe.parse_json(name)
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


# `download_multi_pdf`, `download_multi_pdf_async`, `download_pdf`, `report_to_pdf`, `render_letterhead_for_print`, `print_by_server` moved to frappe.printing.api.
# The aliases keep the old dotted paths working; resolved lazily to avoid
# circular imports.
_MOVED_TO_PRINTING_API = {
	"download_multi_pdf": "download_multi_pdf",
	"download_multi_pdf_async": "download_multi_pdf_async",
	"download_pdf": "download_pdf",
	"report_to_pdf": "report_to_pdf",
	"render_letterhead_for_print": "render_letterhead_for_print",
	"print_by_server": "print_by_server",
}


def __getattr__(name: str):
	if new_name := _MOVED_TO_PRINTING_API.get(name):
		from frappe.printing import api

		return getattr(api, new_name)
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
