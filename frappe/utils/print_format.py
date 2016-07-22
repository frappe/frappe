from __future__ import unicode_literals

import frappe, os, copy, json, re
from frappe import _

from frappe.modules import get_doc_path
from jinja2 import TemplateNotFound
from frappe.utils import cint, strip_html
from frappe.utils.pdf import get_pdf

no_cache = 1
no_sitemap = 1

base_template_path = "templates/www/print.html"
standard_format = "templates/print_formats/standard.html"

@frappe.whitelist()
def download_multi_pdf(doctype, name, format=None):
	# name can include names of many docs of the same doctype.
	totalhtml = ""
	# Pagebreak to be added between each doc html
	pagebreak = """<p style="page-break-after:always;"></p>"""

	options = {}

	import json
	result = json.loads(name)
	# Get html of each doc and combine including page breaks
	for i, ss in enumerate(result):
		html = frappe.get_print(doctype, ss, format)
		if i == len(result)-1:
			totalhtml = totalhtml + html
		else:
			totalhtml = totalhtml + html + pagebreak

	frappe.local.response.filename = "{doctype}.pdf".format(doctype=doctype.replace(" ", "-").replace("/", "-"))

	# Title of pdf
	options.update({
		'title': doctype,
	})

	frappe.local.response.filecontent = get_pdf(totalhtml,options)
	frappe.local.response.type = "download"

@frappe.whitelist()
def download_pdf(doctype, name, format=None, doc=None):
	html = frappe.get_print(doctype, name, format, doc=doc)
	frappe.local.response.filename = "{name}.pdf".format(name=name.replace(" ", "-").replace("/", "-"))
	frappe.local.response.filecontent = get_pdf(html)
	frappe.local.response.type = "download"

@frappe.whitelist()
def report_to_pdf(html):
	frappe.local.response.filename = "report.pdf"
	frappe.local.response.filecontent = get_pdf(html, {"orientation": "Landscape"})
	frappe.local.response.type = "download"