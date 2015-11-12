# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import pdfkit, os, frappe
from frappe.utils import scrub_urls
from frappe import _

def get_pdf(html, options=None):
	if not options:
		options = {}

	options.update({
		"print-media-type": None,
		"background": None,
		"images": None,
		'margin-top': '15mm',
		'margin-right': '15mm',
		'margin-bottom': '15mm',
		'margin-left': '15mm',
		'encoding': "UTF-8",
		'quiet': None,
		'no-outline': None
	})

	if not options.get("page-size"):
		options['page-size'] = frappe.db.get_single_value("Print Settings", "pdf_page_size") or "A4"

	html = scrub_urls(html)
	fname = os.path.join("/tmp", frappe.generate_hash() + ".pdf")

	try:
		pdfkit.from_string(html, fname, options=options or {})

		with open(fname, "rb") as fileobj:
			filedata = fileobj.read()

	except IOError, e:
		if "ContentNotFoundError" in e.message:
			# allow pdfs with missing images if file got created
			if os.path.exists(fname):
				with open(fname, "rb") as fileobj:
					filedata = fileobj.read()

			else:
				frappe.throw(_("PDF generation failed because of broken image links"))
		else:
			raise

	finally:
		# always cleanup
		if os.path.exists(fname):
			os.remove(fname)

	return filedata
