import re
from typing import Literal

import frappe
from frappe.utils.data import cint, cstr

# Chromium download/setup helpers were moved to `frappe.utils.chromium.download`.


def get_print(
	doctype=None,
	name=None,
	print_format=None,
	style=None,
	as_pdf=False,
	doc=None,
	output=None,
	no_letterhead=0,
	password=None,
	pdf_options=None,
	letterhead=None,
	pdf_generator: Literal["wkhtmltopdf", "chrome"] | None = None,
):
	"""Get Print Format for given document.
	:param doctype: DocType of document.
	:param name: Name of document.
	:param print_format: Print Format name. Default 'Standard',
	:param style: Print Format style.
	:param as_pdf: Return as PDF. Default False.
	:param password: Password to encrypt the pdf with. Default None
	:param pdf_generator: PDF generator to use. Default 'wkhtmltopdf'
	"""

	"""
	local.form_dict.pdf_generator is set from before_request hook (print designer app) for download_pdf endpoint
	if it is not set (internal function call) then set it
	"""
	import copy

	from frappe.utils.pdf import get_pdf
	from frappe.website.serve import get_response_without_exception_handling

	local = frappe.local
	if "pdf_generator" not in local.form_dict:
		# if arg is passed, use that, else get setting from print format
		if pdf_generator is None:
			pdf_generator = (
				frappe.get_cached_value("Print Format", print_format, "pdf_generator") or "wkhtmltopdf"
			)
		local.form_dict.pdf_generator = pdf_generator

	original_form_dict = copy.deepcopy(local.form_dict)
	try:
		local.form_dict.doctype = doctype
		local.form_dict.name = name
		local.form_dict.format = print_format
		local.form_dict.style = style
		local.form_dict.doc = doc
		local.form_dict.no_letterhead = no_letterhead
		local.form_dict.letterhead = letterhead

		pdf_options = pdf_options or {}
		if password:
			pdf_options["password"] = password

		response = get_response_without_exception_handling("printview", 200)
		html = str(response.data, "utf-8")
	finally:
		local.form_dict = original_form_dict

	if not as_pdf:
		return html

	if local.form_dict.pdf_generator != "wkhtmltopdf":
		hook_func = frappe.get_hooks("pdf_generator")
		for hook in hook_func:
			"""
			check pdf_generator value in your hook function.
			if it matches run and return pdf else return None
			"""
			pdf = frappe.call(
				hook,
				print_format=print_format,
				html=html,
				options=pdf_options,
				output=output,
				pdf_generator=local.form_dict.pdf_generator,
			)
			# if hook returns a value, assume it was the correct pdf_generator and return it
			if pdf:
				if output and isinstance(pdf, bytes):
					from io import BytesIO

					from pypdf import PdfReader

					reader = PdfReader(BytesIO(pdf))
					for page in reader.pages:
						output.add_page(page)
					return output
				return pdf

	for hook in frappe.get_hooks("on_print_pdf"):
		frappe.call(hook, doctype=doctype, name=name, print_format=print_format)

	return get_pdf(html, options=pdf_options, output=output)


def attach_print(
	doctype,
	name,
	file_name=None,
	print_format=None,
	style=None,
	html=None,
	doc=None,
	lang=None,
	print_letterhead=True,
	password=None,
	letterhead=None,
):
	from frappe.translate import print_language
	from frappe.utils import scrub_urls
	from frappe.utils.pdf import get_pdf

	print_settings = frappe.db.get_singles_dict("Print Settings")
	if print_letterhead and not letterhead:
		if not doc:
			doc = frappe.get_cached_doc(doctype, name)
		letterhead = doc.get("letter_head") or frappe.get_cached_value(
			"Letter Head", {"is_default": 1}, "name"
		)
	kwargs = dict(
		print_format=print_format,
		style=style,
		doc=doc,
		no_letterhead=not print_letterhead,
		letterhead=letterhead,
		password=password,
	)

	frappe.local.flags.ignore_print_permissions = True

	is_beta_print_format = False
	if print_format and print_format != "Standard":
		print_format_doc = frappe.get_cached_doc("Print Format", print_format)
		is_beta_print_format = print_format_doc.get("print_format_builder_beta")

	with print_language(lang or frappe.local.lang):
		content = ""
		if cint(print_settings.send_print_as_pdf):
			ext = ".pdf"
			if html:
				content = get_pdf(html, options={"password": password} if password else None)
			elif is_beta_print_format:
				from frappe.utils.print_format_generator import PrintFormatGenerator

				doc_obj = doc or frappe.get_cached_doc(doctype, name)
				letterhead_name = letterhead if print_letterhead else None
				generator = PrintFormatGenerator(print_format, doc_obj, letterhead_name)
				content = generator.render_pdf()
			else:
				kwargs["as_pdf"] = True
				content = get_print(doctype, name, **kwargs)
		else:
			ext = ".html"
			content = html or scrub_urls(get_print(doctype, name, **kwargs)).encode("utf-8")

	frappe.local.flags.ignore_print_permissions = False

	if not file_name:
		file_name = name
	file_name = cstr(file_name).replace(" ", "").replace("/", "-") + ext

	return {"fname": file_name, "fcontent": content}


def parse_float_and_unit(input_text, default_unit="px"):
	if isinstance(input_text, int | float):
		return {"value": input_text, "unit": default_unit}
	if not isinstance(input_text, str):
		return

	number = float(re.search(r"[+-]?([0-9]*[.])?[0-9]+", input_text).group())
	valid_units = [r"px", r"mm", r"cm", r"in"]
	unit = [match.group() for rx in valid_units if (match := re.search(rx, input_text))]

	return {"value": number, "unit": unit[0] if len(unit) == 1 else default_unit}


def convert_uom(
	number: float,
	from_uom: Literal["px", "mm", "cm", "in"] = "px",
	to_uom: Literal["px", "mm", "cm", "in"] = "px",
	only_number: bool = False,
) -> float:
	unit_values = {
		"px": 1,
		"mm": 3.7795275591,
		"cm": 37.795275591,
		"in": 96,
	}
	from_px = (
		{
			"to_px": 1,
			"to_mm": unit_values["px"] / unit_values["mm"],
			"to_cm": unit_values["px"] / unit_values["cm"],
			"to_in": unit_values["px"] / unit_values["in"],
		},
	)
	from_mm = (
		{
			"to_mm": 1,
			"to_px": unit_values["mm"] / unit_values["px"],
			"to_cm": unit_values["mm"] / unit_values["cm"],
			"to_in": unit_values["mm"] / unit_values["in"],
		},
	)
	from_cm = (
		{
			"to_cm": 1,
			"to_px": unit_values["cm"] / unit_values["px"],
			"to_mm": unit_values["cm"] / unit_values["mm"],
			"to_in": unit_values["cm"] / unit_values["in"],
		},
	)
	from_in = {
		"to_in": 1,
		"to_px": unit_values["in"] / unit_values["px"],
		"to_mm": unit_values["in"] / unit_values["mm"],
		"to_cm": unit_values["in"] / unit_values["cm"],
	}
	converstion_factor = ({"from_px": from_px, "from_mm": from_mm, "from_cm": from_cm, "from_in": from_in},)
	if only_number:
		return round(number * converstion_factor[0][f"from_{from_uom}"][0][f"to_{to_uom}"], 3)
	return f"{round(number * converstion_factor[0][f'from_{from_uom}'][0][f'to_{to_uom}'], 3)}{to_uom}"
