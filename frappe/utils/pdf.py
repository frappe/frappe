# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import base64
import contextlib
import io
import mimetypes
import os
import subprocess
from urllib.parse import parse_qs, urlparse

import cssutils
import pdfkit

pdfkit.source.unicode = str  # NOTE: upstream bug; PYTHONOPTIMIZE=1 optimized this away
from bs4 import BeautifulSoup
from packaging.version import Version
from pypdf import PdfReader, PdfWriter

import frappe
from frappe import _
from frappe.core.doctype.file.utils import find_file_by_url
from frappe.utils import cstr, scrub_urls
from frappe.utils.caching import redis_cache
from frappe.utils.jinja_globals import bundled_asset, is_rtl

cssutils.log.setLog(frappe.logger("cssutils"))

PDF_CONTENT_ERRORS = [
	"ContentNotFoundError",
	"ContentOperationNotPermittedError",
	"UnknownContentError",
	"RemoteHostClosedError",
]


def pdf_header_html(soup, head, content, styles, html_id, css, path=None):
	if not path:
		path = "templates/print_formats/pdf_header_footer.html"
	return frappe.render_template(
		path,
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
	"""Guess line on which exception occurred from current traceback."""
	with contextlib.suppress(Exception):
		import sys
		import traceback

		_, _, tb = sys.exc_info()

		for frame in reversed(traceback.extract_tb(tb)):
			if template.filename in frame.filename:
				return frame.lineno


def pdf_footer_html(soup, head, content, styles, html_id, css, path=None):
	return pdf_header_html(
		soup=soup, head=head, content=content, styles=styles, html_id=html_id, css=css, path=path
	)


def get_pdf(html, options=None, output: PdfWriter | None = None):
	html = scrub_urls(html)
	html, options = prepare_options(html, options)

	options.update({"disable-javascript": "", "disable-local-file-access": ""})

	filedata = ""
	if Version(get_wkhtmltopdf_version()) > Version("0.12.3"):
		options.update({"disable-smart-shrinking": ""})

	try:
		# Set filename property to false, so no file is actually created
		filedata = pdfkit.from_string(html, options=options or {}, verbose=True)

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
	# https://docs.python.org/3/library/io.html
	stream = io.BytesIO()
	writer_obj.write(stream)

	# Change the stream position to start of the stream
	stream.seek(0)

	# Read up to size bytes from the object and return them
	return stream.read()


def prepare_options(html, options):
	if not options:
		options = {}

	options.update(
		{
			"print-media-type": None,
			"background": None,
			"images": None,
			"quiet": None,
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
	html = inline_private_images(html)

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
	options = {}
	soup = BeautifulSoup(html, "html5lib")

	options.update(prepare_header_footer(soup))

	toggle_visible_pdf(soup)

	valid_styles = get_print_format_styles(soup)

	attrs = (
		"margin-top",
		"margin-bottom",
		"margin-left",
		"margin-right",
		"page-size",
		"header-spacing",
		"orientation",
		"page-width",
		"page-height",
	)
	options |= {style.name: style.value for style in valid_styles if style.name in attrs}
	return str(soup), options


def get_print_format_styles(soup: BeautifulSoup) -> list[cssutils.css.Property]:
	"""
	Get styles purely on class 'print-format'.
	Valid:
	1) .print-format { ... }
	2) .print-format, p { ... } | p, .print-format { ... }

	Invalid (applied on child elements):
	1) .print-format p { ... } | .print-format > p { ... }
	2) .print-format #abc { ... }

	Returns:
	[cssutils.css.Property(name='margin-top', value='50mm', priority=''), ...]
	"""
	stylesheet = ""
	style_tags = soup.find_all("style")

	# Prepare a css stylesheet from all the style tags' contents
	for style_tag in style_tags:
		stylesheet += cstr(style_tag.string)

	# Use css parser to tokenize the classes and their styles
	parsed_sheet = cssutils.parseString(stylesheet)

	# Get all styles that are only for .print-format
	valid_styles = []
	for rule in parsed_sheet:
		if not isinstance(rule, cssutils.css.CSSStyleRule):
			continue

		# Allow only .print-format { ... } and .print-format, p { ... }
		# Disallow .print-format p { ... } and .print-format > p { ... }
		if ".print-format" in [x.strip() for x in rule.selectorText.split(",")]:
			valid_styles.extend(entry for entry in rule.style)

	return valid_styles


def inline_private_images(html) -> str:
	soup = BeautifulSoup(html, "html.parser")
	for img in soup.find_all("img"):
		if b64 := _get_base64_image(img["src"]):
			img["src"] = b64
	return str(soup)


def _get_base64_image(src):
	"""Return base64 version of image if user has permission to view it"""
	try:
		parsed_url = urlparse(src)
		path = parsed_url.path
		query = parse_qs(parsed_url.query)
		mime_type = mimetypes.guess_type(path)[0]
		if mime_type is None or not mime_type.startswith("image/"):
			return
		filename = (query.get("fid") and query["fid"][0]) or None
		file = find_file_by_url(path, name=filename)
		if not file or not file.is_private:
			return

		b64_encoded_image = base64.b64encode(file.get_content()).decode()
		return f"data:{mime_type};base64,{b64_encoded_image}"
	except Exception:
		frappe.logger("pdf").error("Failed to convert inline images to base64", exc_info=True)


def prepare_header_footer(soup: BeautifulSoup):
	options = {}

	head = soup.find("head").contents
	styles = soup.find_all("style")

	print_css = bundled_asset("print.bundle.css").lstrip("/")
	css = frappe.read_file(os.path.join(frappe.local.sites_path, print_css))

	# extract header and footer
	for html_id in ("header-html", "footer-html"):
		if content := soup.find(id=html_id):
			content = content.extract()
			# `header/footer-html` are extracted, rendered as html
			# and passed in wkhtmltopdf options (as '--header/footer-html')
			# Remove instances of them from main content for render_template
			for tag in soup.find_all(id=html_id):
				tag.extract()

			toggle_visible_pdf(content)
			id_map = {"header-html": "pdf_header_html", "footer-html": "pdf_footer_html"}
			hook_func = frappe.get_hooks(id_map.get(html_id))
			html = frappe.call(
				hook_func[-1],
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
	for key in ("header-html", "footer-html", "cookie-jar"):
		if options.get(key) and os.path.exists(options[key]):
			os.remove(options[key])


def toggle_visible_pdf(soup):
	for tag in soup.find_all(attrs={"class": "visible-pdf"}):
		# remove visible-pdf class to unhide
		tag.attrs["class"].remove("visible-pdf")

	for tag in soup.find_all(attrs={"class": "hidden-pdf"}):
		# remove tag from html
		tag.extract()


@frappe.whitelist()
@redis_cache(ttl=60 * 60)
def is_wkhtmltopdf_valid():
	try:
		output = subprocess.check_output(["wkhtmltopdf", "--version"])
		return "qt" in output.decode("utf-8").lower()
	except Exception:
		return False


def get_wkhtmltopdf_version():
	wkhtmltopdf_version = frappe.cache.hget("wkhtmltopdf_version", None)

	if not wkhtmltopdf_version:
		try:
			res = subprocess.check_output(["wkhtmltopdf", "--version"])
			wkhtmltopdf_version = res.decode("utf-8").split(" ")[1]
			frappe.cache.hset("wkhtmltopdf_version", None, wkhtmltopdf_version)
		except Exception:
			pass

	return wkhtmltopdf_version or "0"
