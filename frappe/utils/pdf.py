# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import pdfkit, os, frappe, sys
from frappe.utils import scrub_urls
from frappe import _
from bs4 import BeautifulSoup

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
		'no-outline': None,
	})

	#create file from input html based on the divs content or create an empty file
	header_html_file = make_html_file(html, "header")
	footer_html_file = make_html_file(html, "footer")

	#update the printing options like margin-top based on variables in html or predefined settings
	options = read_options_from_html(html, header_html_file[0], footer_html_file[0])

	if frappe.session and frappe.session.sid:
		options['cookie'] = [('sid', '{0}'.format(frappe.session.sid))]

	if not options.get("page-size"):
		options['page-size'] = frappe.db.get_single_value("Print Settings", "pdf_page_size") or "A4"

	html = scrub_urls(html)
	fname = os.path.join("/tmp", frappe.generate_hash() + ".pdf")

	try:
		pdfkit.from_string(html, fname, options=options or {}, )

		with open(fname, "rb") as fileobj:
			filedata = fileobj.read()

	except IOError, e:
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
		# always cleanup
		if os.path.exists(fname):
			os.remove(fname)

	try:
		os.remove(header_html_file[1])
	except:
		pass
	try:
		os.remove(footer_html_file[1])
	except:
		pass
	return filedata



def read_options_from_html(html, header_html_file, footer_html_file):
	options = {}

	soup = BeautifulSoup(html, "html5lib")
	if (header_html_file):
		header_html_file_url = frappe.utils.get_request_site_address() + "/files/" + header_html_file
		options.update({
			'header-html': header_html_file_url,
		})
	if (footer_html_file):
		footer_html_file_url = frappe.utils.get_request_site_address() + "/files/" + footer_html_file
		options.update({
			'footer-html': footer_html_file_url,
		})

	try:
		margin_top = soup.find('span', id='margintop')
		margin_top = margin_top.contents
	except:
		margin_top = "15mm"
	options.update({
		'margin-top': margin_top,
	})

	options.update({
		"print-media-type": None,
		"background": None,
		"images": None,
		'margin-right': '15mm',
		'margin-bottom': '15mm',
		'margin-left': '15mm',
		'encoding': "UTF-8",
		'quiet': None,
		'no-outline': None,
	})
	return options

#this function will copy all head info from the soup of the parent document's html and will then return a head element string
def copy_head_info(soup):
	html_style = ""
	html_styles = soup.findAll('style')
	try:
		for style in html_styles:
			html_style += style.prettify()
	except:
		pass

	try:
		html_head = ''.join(map(str, soup.find('head').contents))
	except:
		html_head = ''

	html_head += """
	  <script>
			function subst() {
				var vars={};
			var x=window.location.search.substring(1).split('&');
			for (var i in x) {var z=x[i].split('=',2);vars[z[0]] = unescape(z[1]);}
			var x=['frompage','topage','page','webpage','section','subsection','subsubsection'];
			for (var i in x) {
			var y = document.getElementsByClassName(x[i]);
			for (var j=0; j<y.length; ++j) y[j].textContent = vars[x[i]];
			}
			}
			subst()
		</script>
	"""
	html_head = "<head>"+ html_head + html_style + "</head>"
	return html_head


#this function will create a file with the contents we need for header and footer
def make_html_file(html, type="header"):

	#make sure we use the correct encoding utf8
	reload(sys)
	sys.setdefaultencoding('utf8')
	soup = BeautifulSoup(html, "html5lib")

	#set doctype to html5
	html_doctype = """<!DOCTYPE html>"""

	#make sure we get all styles / scripts of the parent document
	html_head = copy_head_info(soup)

	#get the header div
	if (type=="header"):
		pdf_header = soup.find('div', id='htmlheader')
	else:
		pdf_header = soup.find('div', id='htmlfooter')

	try:
		html_content = ''.join(map(str, pdf_header))
	except:
		html_content = ''

	#create the html body content
	html_body = """<body onload="subst()" style="margin:0; padding:0;"><div class="print-format"><div class="wrapper">""" + html_content  + """</div></div></body></html>"""

	#create the complete html of the page
	header_html = html_doctype + html_head + html_body

	fname = type
	temp_file = create_temp_html_file(fname, header_html)
	return temp_file

#this function will create a random filename and then return the filename and filepath
def create_temp_html_file(fname, html):
	reload(sys)
	sys.setdefaultencoding('utf8')
	temp_name = fname + os.urandom(16).encode('hex') + ".html"
	fpath = frappe.utils.get_files_path() + "/" + temp_name

	while(os.path.exists(fpath)):
		temp_name = fname + os.urandom(16).encode('hex') + ".html"
		fpath = frappe.utils.get_files_path() + "/" + temp_name

	f = open(fpath,'w')
	f.write(html)
	f.close()
	return temp_name, fpath