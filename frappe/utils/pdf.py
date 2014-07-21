# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import pdfkit, os, frappe

def get_pdf(html, options=None):
	if not options:
		options = {}
	if not options.get("page-size"):
		options['page-size'] = frappe.df.get_single_value("Print Settings", "pdf_page_size") or "A4"

	fname = os.path.join("/tmp", frappe.generate_hash() + ".pdf")
	pdfkit.from_string(html, fname, options=options or {})

	with open(fname, "rb") as fileobj:
		filedata = fileobj.read()

	os.remove(fname)

	return filedata
