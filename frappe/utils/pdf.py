# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import pdfkit, os, frappe
from frappe.utils import scrub_urls
from frappe import _
from bs4 import BeautifulSoup
from PyPDF2 import PdfFileWriter, PdfFileReader

def get_pdf(html, options=None, output = None):
	html = scrub_urls(html)
	html, options = prepare_options(html, options)
	fname = os.path.join("/tmp", "frappe-pdf-{0}.pdf".format(frappe.generate_hash()))

	try:
		pdfkit.from_string(html, fname, options=options or {})
		if output:
			append_pdf(PdfFileReader(file(fname,"rb")),output)
		else:
			with open(fname, "rb") as fileobj:
				filedata = fileobj.read()

	except IOError as e:
		if ("ContentNotFoundError" in e.message
			or "ContentOperationNotPermittedError" in e.message
			or "UnknownContentError" in e.message
			or "RemoteHostClosedError" in e.message):

			# allow pdfs with missing images if file got created
			if os.path.exists(fname):
				with open(fname, "rb") as fileobj:
					filedata = fileobj.read()

			else:
				frappe.throw(_("PDF generation failed because of broken image links"))
		else:
			raise

	finally:
		cleanup(fname, options)

	if output:
		return output

	return filedata

def append_pdf(input,output):
	# Merging multiple pdf files
    [output.addPage(input.getPage(page_num)) for page_num in range(input.numPages)]

def prepare_options(html, options):
	if not options:
		options = {}

	options.update({
		'print-media-type': None,
		'background': None,
		'images': None,
		'quiet': None,
		# 'no-outline': None,
		'encoding': "UTF-8",
		#'load-error-handling': 'ignore',

		# defaults
		'margin-right': '15mm',
		'margin-left': '15mm'
	})

	html, html_options = read_options_from_html(html)
	options.update(html_options or {})

	# cookies
	if frappe.session and frappe.session.sid:
		options['cookie'] = [('sid', '{0}'.format(frappe.session.sid))]

	# page size
	if not options.get("page-size"):
		options['page-size'] = frappe.db.get_single_value("Print Settings", "pdf_page_size") or "A4"

	return html, options

def read_options_from_html(html):
	options = {}
	soup = BeautifulSoup(html, "html5lib")

	# extract pdfkit options from html
	for html_id in ("margin-top", "margin-bottom", "margin-left", "margin-right", "page-size"):
		try:
			tag = soup.find(id=html_id)
			if tag and tag.contents:
				options[html_id] = tag.contents
		except:
			pass

	options.update(prepare_header_footer(soup))

	toggle_visible_pdf(soup)

	return soup.prettify(), options

def prepare_header_footer(soup):
	options = {}

	head = soup.find("head").contents
	styles = soup.find_all("style")

	bootstrap = frappe.read_file(os.path.join(frappe.local.sites_path, "assets/frappe/css/bootstrap.css"))
	fontawesome = frappe.read_file(os.path.join(frappe.local.sites_path, "assets/frappe/css/font-awesome.css"))

	# extract header and footer
	for html_id in ("header-html", "footer-html"):
		content = soup.find(id=html_id)
		if content:
			# there could be multiple instances of header-html/footer-html
			for tag in soup.find_all(id=html_id):
				tag.extract()

			toggle_visible_pdf(content)
			html = frappe.render_template("templates/print_formats/pdf_header_footer.html", {
				"head": head,
				"styles": styles,
				"content": content,
				"html_id": html_id,
				"bootstrap": bootstrap,
				"fontawesome": fontawesome
			})

			# create temp file
			fname = os.path.join("/tmp", "frappe-pdf-{0}.html".format(frappe.generate_hash()))
			with open(fname, "w") as f:
				f.write(html.encode("utf-8"))

			# {"header-html": "/tmp/frappe-pdf-random.html"}
			options[html_id] = fname
		else:
			if html_id == "header-html":
				options["margin-top"] = "15mm"
			elif html_id == "footer-html":
				options["margin-bottom"] = "15mm"

	return options

def cleanup(fname, options):
	if os.path.exists(fname):
		os.remove(fname)

	for key in ("header-html", "footer-html"):
		if options.get(key) and os.path.exists(options[key]):
			os.remove(options[key])

def toggle_visible_pdf(soup):
	for tag in soup.find_all(attrs={"class": "visible-pdf"}):
		# remove visible-pdf class to unhide
		tag.attrs['class'].remove('visible-pdf')

	for tag in soup.find_all(attrs={"class": "hidden-pdf"}):
		# remove tag from html
		tag.extract()
