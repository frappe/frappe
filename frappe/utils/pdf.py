# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import contextlib
import io
import os
import re
import subprocess
from distutils.version import LooseVersion

import pdfkit
from bs4 import BeautifulSoup
from pypdf import PdfReader, PdfWriter

import frappe
from frappe import _
from frappe.utils import scrub_urls
from frappe.utils.jinja_globals import bundled_asset, is_rtl
from frappe.utils.logger import pipe_to_log

PDF_CONTENT_ERRORS = [
	"ContentNotFoundError",
	"ContentOperationNotPermittedError",
	"UnknownContentError",
	"RemoteHostClosedError",
]

logger = frappe.logger("wkhtmltopdf", max_size=100000, file_count=3)
logger.setLevel("INFO")


def pdf_header_html(soup, head, content, styles, html_id, css):
	"""
	Render the HTML for the header of the PDF document.

	Args:
		soup (BeautifulSoup): The BeautifulSoup object representing the HTML document.
		head (str): The HTML content for the head of the document.
		content (str): The HTML content for the body of the document.
		styles (str): The CSS styles to be applied to the document.
		html_id (str): The unique identifier for the HTML document.
		css (str): The CSS content to be applied to the document.

	Returns:
		str: The rendered HTML for the header of the PDF document.
	"""
	return frappe.render_template(
		"templates/print_formats/pdf_header_footer.html",
		{
			"head": head,
			"content": content,
			"styles": styles,
			"html_id": html_id,
			"css": css,
			"lang": frappe.local.lang,
			"layout_direction": "rtl" if is_rtl() else "ltr",
		},
	)


def pdf_body_html(template, args, **kwargs):
	"""
	Render the HTML for the body of the PDF document.

	Args:
		template (Jinja2.Template): The Jinja2 template object.
		args: The arguments to be passed to the template.
		kwargs: Additional keyword arguments to be passed to the template.

	Returns:
		str: The rendered HTML for the body of the PDF document.

	Raises:
		frappe.PrintFormatError: If there is an error rendering the template.
	"""
	try:
		return template.render(args, filters={"len": len})
	except Exception as e:
		# Guess line number ?
		frappe.throw(
			_("Error in print format on line {0}: {1}").format(
				_guess_template_error_line_number(template), e
			),
			exc=frappe.PrintFormatError,
			title=_("Print Format Error"),
		)


def _guess_template_error_line_number(template) -> int | None:
	"""Guess line on which exception occured from current traceback."""
	with contextlib.suppress(Exception):
		import sys
		import traceback

		_, _, tb = sys.exc_info()

		for frame in reversed(traceback.extract_tb(tb)):
			if template.filename in frame.filename:
				return frame.lineno


def pdf_footer_html(soup, head, content, styles, html_id, css):
	"""Return the result of calling 'pdf_header_html' with the given parameters."""
	return pdf_header_html(
		soup=soup, head=head, content=content, styles=styles, html_id=html_id, css=css
	)


def get_pdf(html, options=None, output: PdfWriter | None = None):
	"""
	Convert HTML to a PDF using wkhtmltopdf.

	Args:
		html (str): The HTML content to convert.
		options (dict, optional): Additional options for the conversion. Defaults to None.
		output (PdfWriter | None, optional): The output object to append the
			PDF pages to. Defaults to None.

	Returns:
		bytes | PdfWriter | None: The PDF data as bytes if output is None, the
		output object if specified, or None if an error occurs.
	"""
	html = scrub_urls(html)
	html, options = prepare_options(html, options)

	options.update({"disable-javascript": "", "disable-local-file-access": ""})

	filedata = ""
	if LooseVersion(get_wkhtmltopdf_version()) > LooseVersion("0.12.3"):
		options.update({"disable-smart-shrinking": ""})

	try:
		# wkhtmltopdf writes the pdf to stdout and errors to stderr
		# pdfkit v1.0.0 writes the pdf to file or returns it
		# stderr is written to sys.stdout if verbose=True is supplied
		# Set filename property to false, so no file is actually created
		# defaults to redirecting stdout
		with pipe_to_log(logger.info):
			filedata = pdfkit.from_string(html, False, options=options or {}, verbose=True)

		# create in-memory binary streams from filedata and create a PdfReader object
		reader = PdfReader(io.BytesIO(filedata))
	except OSError as e:
		if any([error in str(e) for error in PDF_CONTENT_ERRORS]):
			if not filedata:
				print(html, options)
				frappe.throw(_("PDF generation failed because of broken image links"))

			# allow pdfs with missing images if file got created
			if output:
				output.append_pages_from_reader(reader)
		else:
			raise
	finally:
		cleanup(options)

	if "password" in options:
		password = options["password"]

	if output:
		output.append_pages_from_reader(reader)
		return output

	writer = PdfWriter()
	writer.append_pages_from_reader(reader)

	if "password" in options:
		writer.encrypt(password)

	filedata = get_file_data_from_writer(writer)

	return filedata


def get_file_data_from_writer(writer_obj):
	"""
	Get file data from a writer object.

	This function takes a writer object as input, writes the data from the writer
	object to a stream using the 'write' method, and then reads the data from
	the stream and returns it.

	Args:
		writer_obj: The writer object.

	Returns:
		bytes: The data read from the stream.
	"""

	# https://docs.python.org/3/library/io.html
	stream = io.BytesIO()
	writer_obj.write(stream)

	# Change the stream position to start of the stream
	stream.seek(0)

	# Read up to size bytes from the object and return them
	return stream.read()


def prepare_options(html, options):
	"""
	Prepare options for generating a PDF.

	This function takes 'html' and 'options' as inputs, updates the 'options'
	dictionary with default values for various keys if they are not already
	present, reads additional options from the 'html' string, updates the
	'options' dictionary with cookie options, and finally sets the 'page-size'
	key in the 'options' dictionary based on the value of 'pdf_page_size' from
	the 'Print
	Settings' table or the default value 'A4'.

	Args:
		html (str): The HTML string.
		options (dict): The options dictionary.

	Returns:
		tuple: A tuple containing the updated 'html' string and the updated
		'options' dictionary.
	"""
	if not options:
		options = {}

	options.update(
		{
			"print-media-type": None,
			"background": None,
			"images": None,
			# 'no-outline': None,
			"encoding": "UTF-8",
			# 'load-error-handling': 'ignore'
		}
	)

	if not options.get("margin-right"):
		options["margin-right"] = "15mm"

	if not options.get("margin-left"):
		options["margin-left"] = "15mm"

	html, html_options = read_options_from_html(html)
	options.update(html_options or {})

	# cookies
	options.update(get_cookie_options())

	# page size
	pdf_page_size = (
		options.get("page-size") or frappe.db.get_single_value("Print Settings", "pdf_page_size") or "A4"
	)

	if pdf_page_size == "Custom":
		options["page-height"] = options.get("page-height") or frappe.db.get_single_value(
			"Print Settings", "pdf_page_height"
		)
		options["page-width"] = options.get("page-width") or frappe.db.get_single_value(
			"Print Settings", "pdf_page_width"
		)
	else:
		options["page-size"] = pdf_page_size

	return html, options


def get_cookie_options():
	"""
	Get the options for setting cookies using the wkhtmltopdf's cookie-jar feature.

	This function checks if a session is active and if frappe.local.request is
	available. If so, it generates a temporary cookie jar file using
	frappe.generate_hash() and sets the 'sid' cookie with the domain
	restricted to the host domain.

	Returns:
		dict: A dictionary of options.
	"""
	options = {}
	if frappe.session and frappe.session.sid and hasattr(frappe.local, "request"):
		# Use wkhtmltopdf's cookie-jar feature to set cookies and restrict them to host domain
		cookiejar = f"/tmp/{frappe.generate_hash()}.jar"

		# Remove port from request.host
		# https://werkzeug.palletsprojects.com/en/0.16.x/wrappers/#werkzeug.wrappers.BaseRequest.host
		domain = frappe.utils.get_host_name().split(":", 1)[0]
		with open(cookiejar, "w") as f:
			f.write(f"sid={frappe.session.sid}; Domain={domain};\n")

		options["cookie-jar"] = cookiejar

	return options


def read_options_from_html(html):
	"""
	Read options from an HTML string and return the modified HTML and options.

	This function takes an HTML string as input, parses it using BeautifulSoup, and
	extracts specific options.
	It calls the prepare_header_footer() function to update the options dictionary
	with header and footer information.
	It also calls the toggle_visible_pdf() function to modify the HTML by removing
	elements that should not be visible in the PDF.
	Finally, it uses regular expressions to extract options related to margin, page
	size, orientation, and page dimensions.

	Args:
		html (str): The HTML string.

	Returns:
		tuple: A tuple containing the modified HTML string and a dictionary of options.
	"""
	options = {}
	soup = BeautifulSoup(html, "html5lib")

	options.update(prepare_header_footer(soup))

	toggle_visible_pdf(soup)

	# use regex instead of soup-parser
	for attr in (
		"margin-top",
		"margin-bottom",
		"margin-left",
		"margin-right",
		"page-size",
		"header-spacing",
		"orientation",
		"page-width",
		"page-height",
	):
		try:
			pattern = re.compile(r"(\.print-format)([\S|\s][^}]*?)(" + str(attr) + r":)(.+)(mm;)")
			match = pattern.findall(html)
			if match:
				options[attr] = str(match[-1][3]).strip()
		except Exception:
			pass

	return str(soup), options


def prepare_header_footer(soup):
	"""
	Prepare the header and footer options for generating a PDF.

	Args:
		soup (BeautifulSoup): A BeautifulSoup object representing the HTML.

	Returns:
		dict: A dictionary containing the options for the header and footer.
	"""
	options = {}

	head = soup.find("head").contents
	styles = soup.find_all("style")

	print_css = bundled_asset("print.bundle.css").lstrip("/")
	css = frappe.read_file(os.path.join(frappe.local.sites_path, print_css))

	# extract header and footer
	for html_id in ("header-html", "footer-html"):
		content = soup.find(id=html_id)
		if content:
			# there could be multiple instances of header-html/footer-html
			for tag in soup.find_all(id=html_id):
				tag.extract()

			toggle_visible_pdf(content)
			id_map = {"header-html": "pdf_header_html", "footer-html": "pdf_footer_html"}
			hook_func = frappe.get_hooks(id_map.get(html_id))
			html = frappe.get_attr(hook_func[-1])(
				soup=soup,
				head=head,
				content=content,
				styles=styles,
				html_id=html_id,
				css=css,
			)

			# create temp file
			fname = os.path.join("/tmp", f"frappe-pdf-{frappe.generate_hash()}.html")
			with open(fname, "wb") as f:
				f.write(html.encode("utf-8"))

			# {"header-html": "/tmp/frappe-pdf-random.html"}
			options[html_id] = fname
		else:
			if html_id == "header-html":
				options["margin-top"] = "15mm"
			elif html_id == "footer-html":
				options["margin-bottom"] = "15mm"

	return options


def cleanup(options):
	"""
	Remove files specified in the 'options' dictionary.

	This function iterates over the 'options' dictionary and removes files
	associated with specific keys if they exist on the file system.

	Args:
		options (dict): A dictionary containing the options.
	"""
	for key in ("header-html", "footer-html", "cookie-jar"):
		if options.get(key) and os.path.exists(options[key]):
			os.remove(options[key])


def toggle_visible_pdf(soup):
	"""
	Toggle the visibility of elements in a BeautifulSoup object.

	This function finds all elements with the class 'visible-pdf' and removes
	the 'visible-pdf' class to unhide them. It also removes all elements with
	the class 'hidden-pdf' from the HTML.

	Args:
		soup (BeautifulSoup): The BeautifulSoup object.
	"""
	for tag in soup.find_all(attrs={"class": "visible-pdf"}):
		# remove visible-pdf class to unhide
		tag.attrs["class"].remove("visible-pdf")

	for tag in soup.find_all(attrs={"class": "hidden-pdf"}):
		# remove tag from html
		tag.extract()


def get_wkhtmltopdf_version():
	"""
	Get the version of wkhtmltopdf.

	This function retrieves the version of wkhtmltopdf by checking the value
	stored in a cache. If the value is not found in the cache, it attempts to
	run the 'wkhtmltopdf --version' command and stores the version in the
	cache.

	Returns:
		str: The version of wkhtmltopdf.
	"""
	wkhtmltopdf_version = frappe.cache.hget("wkhtmltopdf_version", None)

	if not wkhtmltopdf_version:
		try:
			res = subprocess.check_output(["wkhtmltopdf", "--version"])
			wkhtmltopdf_version = res.decode("utf-8").split(" ")[1]
			frappe.cache.hset("wkhtmltopdf_version", None, wkhtmltopdf_version)
		except Exception:
			pass

	return wkhtmltopdf_version or "0"
