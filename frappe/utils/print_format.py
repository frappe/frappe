from __future__ import unicode_literals

import frappe, os, copy, json, re
from frappe import _

from frappe.modules import get_doc_path
from jinja2 import TemplateNotFound
from frappe.utils import cint, strip_html
from frappe.utils.pdf import get_pdf,cleanup
import cups
from PyPDF2 import PdfFileWriter, PdfFileReader

no_cache = 1
no_sitemap = 1

base_template_path = "templates/www/printview.html"
standard_format = "templates/print_formats/standard.html"

@frappe.whitelist()
def download_multi_pdf(doctype, name, format=None):
	# name can include names of many docs of the same doctype.

	import json
	result = json.loads(name)

	# Concatenating pdf files
	output = PdfFileWriter()
	for i, ss in enumerate(result):
		output = frappe.get_print(doctype, ss, format, as_pdf = True, output = output)

	frappe.local.response.filename = "{doctype}.pdf".format(doctype=doctype.replace(" ", "-").replace("/", "-"))
	frappe.local.response.filecontent = read_multi_pdf(output)
	frappe.local.response.type = "download"

def read_multi_pdf(output):
	# Get the content of the merged pdf files
	fname = os.path.join("/tmp", "frappe-pdf-{0}.pdf".format(frappe.generate_hash()))
	output.write(open(fname,"wb"))

	with open(fname, "rb") as fileobj:
		filedata = fileobj.read()

	return filedata

@frappe.whitelist()
def download_pdf(doctype, name, format=None, doc=None, no_letterhead=0):
	html = frappe.get_print(doctype, name, format, doc=doc, no_letterhead=no_letterhead)
	frappe.local.response.filename = "{name}.pdf".format(name=name.replace(" ", "-").replace("/", "-"))
	frappe.local.response.filecontent = get_pdf(html)
	frappe.local.response.type = "download"

@frappe.whitelist()
def report_to_pdf(html, orientation="Landscape"):
	frappe.local.response.filename = "report.pdf"
	frappe.local.response.filecontent = get_pdf(html, {"orientation": orientation})
	frappe.local.response.type = "download"

@frappe.whitelist()
def print_by_server(doctype, name, format=None, doc=None, no_letterhead=0):
	print_settings = frappe.get_doc("Print Settings")
	try:
		cups.setServer(print_settings.server_ip)
		cups.setPort(print_settings.port)
		conn = cups.Connection()
		output = PdfFileWriter()
		output = frappe.get_print(doctype, name, format, doc=doc, no_letterhead=no_letterhead, as_pdf = True, output = output)
		file = os.path.join("/tmp", "frappe-pdf-{0}.pdf".format(frappe.generate_hash()))
		output.write(open(file,"wb"))
		conn.printFile(print_settings.printer_name,file , name, {})
	except IOError as e:
		if ("ContentNotFoundError" in e.message
			or "ContentOperationNotPermittedError" in e.message
			or "UnknownContentError" in e.message
			or "RemoteHostClosedError" in e.message):
			frappe.throw(_("PDF generation failed"))
	except cups.IPPError:
		frappe.throw(_("Printing failed"))
	finally:
		cleanup(file,{})
