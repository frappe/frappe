# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import contextlib
from typing import TYPE_CHECKING

import frappe
from frappe import _
from frappe.utils import cstr
from frappe.utils.data import get_url
from frappe.utils.jinja_globals import is_rtl

if TYPE_CHECKING:
	import cssutils
	from bs4 import BeautifulSoup
	from pypdf import PdfReader, PdfWriter


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
				_guess_template_error_line_number(template), str(e)
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


def measure_time(func):
	import time

	def wrapper(*args, **kwargs):
		start_time = time.time()
		result = func(*args, **kwargs)
		end_time = time.time()
		if frappe.conf.developer_mode:
			print(f"Function {func.__name__} took {end_time - start_time:.4f} seconds")
		return result

	return wrapper


@measure_time
def get_pdf(
	html: str,
	options: dict | None = None,
	output: "PdfWriter" | None = None,
	print_format: str | None = None,
):
	"""Render `html` to PDF with Chromium."""
	from frappe.utils.chromium import ChromiumManager
	from frappe.utils.pdf_generator.browser import Browser
	from frappe.utils.pdf_generator.pdf_merge import PDFTransformer

	generator, token = ChromiumManager.acquire()
	try:
		browser = Browser(generator, print_format, html, options or {})
		return PDFTransformer(browser).transform_pdf(output=output)
	finally:
		generator.release(token)


def get_chrome_pdf(print_format, html, options, output, pdf_generator=None):
	if pdf_generator != "chrome":
		return
	return get_pdf(html, options, output, print_format=print_format)


def get_print_format_styles(soup: "BeautifulSoup") -> list["cssutils.css.Property"]:
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
	import cssutils

	cssutils.log.setLog(frappe.logger("cssutils"))

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


def toggle_visible_pdf(soup):
	for tag in soup.find_all(attrs={"class": "visible-pdf"}):
		# remove visible-pdf class to unhide
		tag.attrs["class"].remove("visible-pdf")

	for tag in soup.find_all(attrs={"class": "hidden-pdf"}):
		# remove tag from html
		tag.extract()


def pdf_contains_js(file_content: bytes):
	"""
	Check if a PDF file contains JavaScript.

	Args:
		file_content (bytes): The content of the PDF file.

	Returns:
		bool: True if the PDF contains JavaScript, False otherwise and also if the file is encrypted.
	"""
	from io import BytesIO

	from pypdf import PdfReader, errors
	from pypdf.generic import IndirectObject

	reader = PdfReader(BytesIO(file_content))

	def has_javascript(obj, seen=None):
		if seen is None:
			seen = set()
		if isinstance(obj, IndirectObject):
			key = (obj.idnum, obj.generation)
			if key in seen:
				return False
			seen.add(key)
			obj = obj.get_object()
		if isinstance(obj, dict):
			for key, value in obj.items():
				if key == "/Parent":
					continue
				if key in ("/JS", "/JavaScript"):
					return True
				if has_javascript(value, seen):
					return True
		elif isinstance(obj, list):
			for item in obj:
				if has_javascript(item, seen):
					return True
		return False

	root = reader.trailer.get("/Root", {})

	try:
		if has_javascript(root):
			return True

		for page in reader.pages:
			if has_javascript(page):
				return True
	except errors.FileNotDecryptedError:
		# resolving any indirect object (root, page, or otherwise) requires
		# decryption; an encrypted file we can't decrypt is treated as not
		# containing JS, same as an unreadable/undecryptable file always was
		pass

	return False


def _reader_has_signature(reader: "PdfReader") -> bool:
	"""Check an already-open PdfReader for a signed digital-signature field.

	Optimizing a signed PDF would silently break its signature,
	so callers should skip optimization when this returns True.

	Returns True (fail-safe) if the fields can't be inspected.
	"""
	from pypdf.errors import PyPdfError

	try:
		fields = reader.get_fields() or {}
		return any(field.get("/FT") == "/Sig" and field.get("/V") for field in fields.values())
	except (PyPdfError, KeyError, ValueError):
		return True


def _pdf_has_oversized_image(reader: "PdfReader", max_pixels: int) -> bool:
	"""Check declared image XObject dimensions without decoding any pixel data.
	Avoid exhausting memory in loading image.
	"""
	for page in reader.pages:
		try:
			xobjects = page["/Resources"]["/XObject"]
		except KeyError:
			continue
		for xobj in xobjects.values():
			xobj = xobj.get_object()
			if xobj.get("/Subtype") != "/Image":
				continue
			width = int(xobj.get("/Width", 0))
			height = int(xobj.get("/Height", 0))
			if width * height > max_pixels:
				return True
	return False


def optimize_pdf(content: bytes, quality: int = 85, max_dim: int = 1600) -> bytes:
	"""Recompress embedded raster images and compress content streams to shrink a PDF.

	Only benefits image-heavy PDFs (e.g. scanned documents); text/vector-only PDFs
	won't shrink meaningfully. Falls back to the original content if optimization
	fails, doesn't actually reduce the size, if the PDF is digitally signed, or if
	it contains an image large enough to risk exhausting memory on decode.
	"""
	import zlib
	from io import BytesIO

	from PIL import Image, UnidentifiedImageError
	from pypdf import PdfReader, PdfWriter
	from pypdf.errors import PyPdfError

	try:
		reader = PdfReader(BytesIO(content))

		if _reader_has_signature(reader):
			return content

		if _pdf_has_oversized_image(reader, Image.MAX_IMAGE_PIXELS):
			return content

		writer = PdfWriter(clone_from=reader)

		unexpected_image_error_logged = False
		for page in writer.pages:
			for image_id in page.images.keys():
				try:
					img_file = page.images[image_id]
					image = img_file.image
					if image.width > max_dim or image.height > max_dim:
						image.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
					img_file.replace(image, quality=quality, optimize=True)
				except (
					PyPdfError,
					UnidentifiedImageError,
					Image.DecompressionBombError,
					OSError,
					ValueError,
					EOFError,
					zlib.error,
				):
					# skip this image rather than abandoning the whole document
					continue
				except Exception:
					if not unexpected_image_error_logged:
						frappe.log_error(
							title=_("Unexpected error while optimizing one image in PDF"),
							defer_insert=True,
						)
						unexpected_image_error_logged = True
					continue
			page.compress_content_streams()  # This is CPU intensive!

		writer.compress_identical_objects(remove_duplicates=True, remove_unreferenced=True)

		output = BytesIO()
		writer.write(output)
		optimized_content = output.getvalue()
		return optimized_content if len(optimized_content) < len(content) else content
	except (
		PyPdfError,
		UnidentifiedImageError,
		Image.DecompressionBombError,
		OSError,
		ValueError,
		EOFError,
		zlib.error,
	) as e:
		frappe.msgprint(_("Failed to optimize PDF: {0}").format(str(e)))
		return content
	except Exception:
		frappe.log_error(title=_("Unexpected error while optimizing PDF"))
		return content


def get_host_url():
	if frappe.request:
		return frappe.request.host_url
	else:
		return get_url() + "/"
