# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import copy
import json
import os
import re
from typing import TYPE_CHECKING, Optional, TypedDict

import frappe
from frappe import _, cstr, get_module_path
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.core.doctype.document_share_key.document_share_key import is_expired
from frappe.utils import cint, escape_html, strip_html
from frappe.utils.jinja_globals import is_rtl

if TYPE_CHECKING:
	from frappe.core.doctype.docfield.docfield import DocField
	from frappe.model.document import Document
	from frappe.model.meta import Meta
	from frappe.printing.doctype.print_format.print_format import PrintFormat
	from frappe.printing.doctype.print_settings.print_settings import PrintSettings

no_cache = 1

standard_format = "templates/print_formats/standard.html"


class PrintContext(TypedDict):
	body: str
	print_style: str
	comment: str
	title: str
	lang: str
	layout_direction: str
	doctype: str
	name: str
	key: str


def get_context(context) -> PrintContext:
	"""Build context for print"""
	if not ((frappe.form_dict.doctype and frappe.form_dict.name) or frappe.form_dict.doc):
		return PrintContext(
			print_style="",
			comment="",
			title="Error",
			lang="en",
			layout_direction="ltr",
			doctype="",
			name="",
			key="",
			body=f"""
<h1>Error</h1>
<p>Parameters doctype and name required</p>
<pre>{escape_html(frappe.as_json(frappe.form_dict, indent=2))}</pre>
""",
		)

	if frappe.form_dict.doc:
		doc = frappe.form_dict.doc
	else:
		doc = frappe.get_lazy_doc(frappe.form_dict.doctype, frappe.form_dict.name)

	set_link_titles(doc)

	settings = frappe.parse_json(frappe.form_dict.settings)

	letterhead = frappe.form_dict.letterhead or None

	meta = frappe.get_meta(doc.doctype)

	print_format = get_print_format_doc(None, meta=meta)

	if print_format and print_format.get("print_format_builder_beta"):
		from frappe.utils.weasyprint import get_html

		body = get_html(
			doctype=frappe.form_dict.doctype, name=frappe.form_dict.name, print_format=print_format.name
		)
		body += trigger_print_script
	else:
		body = get_rendered_template(
			doc,
			print_format=print_format,
			meta=meta,
			trigger_print=frappe.form_dict.trigger_print,
			no_letterhead=frappe.form_dict.no_letterhead,
			letterhead=letterhead,
			settings=settings,
		)

	# Include selected print format name in access log
	print_format_name = getattr(print_format, "name", "Standard")

	make_access_log(
		doctype=frappe.form_dict.doctype,
		document=frappe.form_dict.name,
		file_type="PDF",
		method="Print",
		page=f"Print Format: {print_format_name}",
	)

	return {
		"body": body,
		"print_style": get_print_style(frappe.form_dict.style, print_format),
		"comment": frappe.session.user,
		"title": frappe.utils.strip_html(cstr(doc.get_title() or doc.name)),
		"lang": frappe.local.lang,
		"layout_direction": "rtl" if is_rtl() else "ltr",
		"doctype": frappe.form_dict.doctype,
		"name": frappe.form_dict.name,
		"key": frappe.form_dict.get("key"),
		"print_format": print_format_name,
		"letterhead": letterhead,
		"no_letterhead": frappe.form_dict.no_letterhead,
		"pdf_generator": frappe.form_dict.get("pdf_generator", "wkhtmltopdf"),
	}


def get_print_format_doc(print_format_name: str, meta: "Meta") -> Optional["PrintFormat"]:
	"""Return print format document."""
	if not print_format_name:
		print_format_name = frappe.form_dict.format or meta.default_print_format or "Standard"

	if print_format_name == "Standard":
		return None
	else:
		try:
			return frappe.get_doc("Print Format", print_format_name)
		except frappe.DoesNotExistError:
			# if old name, return standard!
			return None


def get_rendered_template(
	doc: "Document",
	print_format: Optional["PrintFormat"] = None,
	meta: "Meta" = None,
	no_letterhead: bool | None = None,
	letterhead: str | None = None,
	trigger_print: bool = False,
	settings: dict | None = None,
) -> str:
	if not frappe.flags.ignore_print_permissions:
		validate_print_permission(doc)

	print_settings = frappe.get_single("Print Settings").as_dict()
	print_settings.update(settings or {})

	if isinstance(no_letterhead, str):
		no_letterhead = cint(no_letterhead)

	elif no_letterhead is None:
		no_letterhead = not cint(print_settings.with_letterhead)

	doc.flags.in_print = True
	doc.flags.print_settings = print_settings

	if doc.meta.is_submittable:
		if doc.docstatus.is_draft() and not cint(print_settings.allow_print_for_draft):
			frappe.throw(_("Not allowed to print draft documents"), frappe.PermissionError)

		if doc.docstatus.is_cancelled() and not cint(print_settings.allow_print_for_cancelled):
			frappe.throw(_("Not allowed to print cancelled documents"), frappe.PermissionError)

	doc.run_method("before_print", print_settings)

	if not hasattr(doc, "print_heading"):
		doc.print_heading = None
	if not hasattr(doc, "sub_heading"):
		doc.sub_heading = None

	if not meta:
		meta = frappe.get_meta(doc.doctype)

	jenv = frappe.get_jenv()
	format_data, format_data_map = [], {}

	# determine template
	if print_format:
		doc.print_section_headings = print_format.show_section_headings
		doc.print_line_breaks = print_format.line_breaks
		doc.align_labels_right = print_format.align_labels_right
		doc.absolute_value = print_format.absolute_value

		def get_template_from_string():
			return jenv.from_string(get_print_format(doc.doctype, print_format))

		template = None
		if hook_func := frappe.get_hooks("get_print_format_template"):
			template = frappe.call(hook_func[-1], jenv=jenv, print_format=print_format)

		if template:
			pass
		elif print_format.custom_format:
			template = get_template_from_string()

		elif print_format.format_data:
			# set format data
			format_data = json.loads(print_format.format_data)
			for df in format_data:
				format_data_map[df.get("fieldname")] = df
				if "visible_columns" in df:
					for _df in df.get("visible_columns"):
						format_data_map[_df.get("fieldname")] = _df

			doc.format_data_map = format_data_map

			template = "standard"

		elif print_format.standard == "Yes":
			template = get_template_from_string()

		else:
			# fallback
			template = "standard"

	else:
		template = "standard"

	if template == "standard":
		template = jenv.get_template(standard_format)

	letter_head = frappe._dict(get_letter_head(doc, no_letterhead, letterhead) or {})

	if letter_head.content:
		letter_head.content = frappe.utils.jinja.render_template(letter_head.content, {"doc": doc.as_dict()})
		if letter_head.header_script:
			letter_head.content += f"""
				<script>
					{ letter_head.header_script }
				</script>
			"""

	if letter_head.footer:
		letter_head.footer = frappe.utils.jinja.render_template(letter_head.footer, {"doc": doc.as_dict()})
		if letter_head.footer_script:
			letter_head.footer += f"""
				<script>
					{ letter_head.footer_script }
				</script>
			"""

	convert_markdown(doc)

	args = {}
	# extract `print_heading_template` from the first field and remove it
	if format_data and format_data[0].get("fieldname") == "print_heading_template":
		args["print_heading_template"] = format_data.pop(0).get("options")

	args.update(
		{
			"doc": doc,
			"meta": frappe.get_meta(doc.doctype),
			"layout": make_layout(doc, meta, format_data),
			"no_letterhead": no_letterhead,
			"trigger_print": cint(trigger_print),
			"letter_head": letter_head.content,
			"footer": letter_head.footer,
			"print_settings": print_settings,
		}
	)
	hook_func = frappe.get_hooks("pdf_body_html")
	html = frappe.get_attr(hook_func[-1])(jenv=jenv, template=template, print_format=print_format, args=args)

	if cint(trigger_print):
		html += trigger_print_script

	return html


def set_link_titles(doc: "Document") -> None:
	# Adds name with title of link field doctype to __link_titles
	if not doc.get("__link_titles"):
		setattr(doc, "__link_titles", {})

	meta = frappe.get_meta(doc.doctype)
	set_title_values_for_link_and_dynamic_link_fields(meta, doc)
	set_title_values_for_table_and_multiselect_fields(meta, doc)


def set_title_values_for_link_and_dynamic_link_fields(
	meta: "Meta", doc: "Document", parent_doc: Optional["Document"] = None
) -> None:
	if parent_doc and not parent_doc.get("__link_titles"):
		setattr(parent_doc, "__link_titles", {})
	elif doc and not doc.get("__link_titles"):
		setattr(doc, "__link_titles", {})

	for field in meta.get_link_fields() + meta.get_dynamic_link_fields():
		if not doc.get(field.fieldname):
			continue

		# If link field, then get doctype from options
		# If dynamic link field, then get doctype from dependent field
		doctype = field.options if field.fieldtype == "Link" else doc.get(field.options)

		meta = frappe.get_meta(doctype)
		if not meta or not meta.title_field or not meta.show_title_field_in_link:
			continue

		link_title = frappe.get_cached_value(doctype, doc.get(field.fieldname), meta.title_field)
		if parent_doc:
			parent_doc.__link_titles[f"{doctype}::{doc.get(field.fieldname)}"] = link_title
		elif doc:
			doc.__link_titles[f"{doctype}::{doc.get(field.fieldname)}"] = link_title


def set_title_values_for_table_and_multiselect_fields(meta: "Meta", doc: "Document") -> None:
	for field in meta.get_table_fields():
		if not doc.get(field.fieldname):
			continue

		_meta = frappe.get_meta(field.options)
		for value in doc.get(field.fieldname):
			set_title_values_for_link_and_dynamic_link_fields(_meta, value, doc)


def convert_markdown(doc: "Document") -> None:
	"""Convert text field values to markdown if necessary."""
	for field in doc.meta.fields:
		if field.fieldtype == "Text Editor":
			value = doc.get(field.fieldname)
			if value and "<!-- markdown -->" in value:
				doc.set(field.fieldname, frappe.utils.md_to_html(value))


@frappe.whitelist()
def get_html_and_style(
	doc: str,
	name: str | None = None,
	print_format: str | None = None,
	no_letterhead: bool | None = None,
	letterhead: str | None = None,
	trigger_print: bool = False,
	style: str | None = None,
	settings: str | None = None,
) -> dict[str, str | None]:
	"""Return `html` and `style` of print format, used in PDF etc."""

	if isinstance(name, str):
		document = frappe.get_lazy_doc(doc, name)
	else:
		document = frappe.get_doc(json.loads(doc))

	document.check_permission()

	print_format = get_print_format_doc(print_format, meta=document.meta)
	set_link_titles(document)

	try:
		html = get_rendered_template(
			doc=document,
			print_format=print_format,
			meta=document.meta,
			no_letterhead=no_letterhead,
			letterhead=letterhead,
			trigger_print=trigger_print,
			settings=frappe.parse_json(settings),
		)
	except frappe.TemplateNotFoundError:
		frappe.clear_last_message()
		html = None

	return {"html": html, "style": get_print_style(style=style, print_format=print_format)}


@frappe.whitelist()
def get_rendered_raw_commands(doc: str, name: str | None = None, print_format: str | None = None) -> dict:
	"""Return Rendered Raw Commands of print format, used to send directly to printer."""

	if isinstance(name, str):
		document = frappe.get_lazy_doc(doc, name)
	else:
		document = frappe.get_doc(json.loads(doc))

	document.check_permission()

	print_format = get_print_format_doc(print_format, meta=document.meta)

	if not print_format or (print_format and not print_format.raw_printing):
		frappe.throw(
			_("{0} is not a raw printing format.").format(print_format), frappe.TemplateNotFoundError
		)

	return {
		"raw_commands": get_rendered_template(doc=document, print_format=print_format, meta=document.meta)
	}


def validate_print_permission(doc: "Document") -> None:
	for ptype in ("read", "print"):
		if frappe.has_permission(doc.doctype, ptype, doc):
			return

	if frappe.has_website_permission(doc):
		return

	if (key := frappe.form_dict.key) and isinstance(key, str) and validate_key(key, doc) is not False:
		return

	doc._handle_permission_failure("print")


def validate_key(key: str, doc: "Document") -> None:
	document_key_expiry = frappe.get_cached_value(
		"Document Share Key",
		{"reference_doctype": doc.doctype, "reference_docname": doc.name, "key": key},
		["expires_on"],
	)
	if document_key_expiry is not None:
		if is_expired(document_key_expiry[0]):
			raise frappe.exceptions.LinkExpired
		else:
			return

	# TODO: Deprecate this! kept it for backward compatibility
	if frappe.get_system_settings("allow_older_web_view_links") and key == doc.get_signature():
		return

	return False


def get_letter_head(doc: "Document", no_letterhead: bool, letterhead: str | None = None) -> dict:
	if no_letterhead:
		return {}

	letterhead_name = letterhead or doc.get("letter_head")
	if letterhead_name:
		return frappe.db.get_value(
			"Letter Head",
			letterhead_name,
			["content", "footer", "header_script", "footer_script"],
			as_dict=True,
		)
	else:
		return (
			frappe.db.get_value(
				"Letter Head",
				{"is_default": 1},
				["content", "footer", "header_script", "footer_script"],
				as_dict=True,
			)
			or {}
		)


def get_print_format(doctype: str, print_format: "PrintFormat") -> str:
	if print_format.disabled:
		frappe.throw(_("Print Format {0} is disabled").format(print_format.name), frappe.DoesNotExistError)

	# server, find template
	module = print_format.module or frappe.db.get_value("DocType", doctype, "module")

	is_custom_module = frappe.get_cached_value("Module Def", module, "custom")

	if not is_custom_module:
		path = os.path.join(
			get_module_path(module, "Print Format", print_format.name),
			frappe.scrub(print_format.name) + ".html",
		)
		if os.path.exists(path):
			with open(path) as pffile:
				return pffile.read()

	if print_format.raw_printing:
		return print_format.raw_commands
	if print_format.html:
		return print_format.html

	frappe.throw(_("No template found at path: {0}").format(path), frappe.TemplateNotFoundError)


def make_layout(doc: "Document", meta: "Meta", format_data=None) -> list:
	"""Builds a hierarchical layout object from the fields list to be rendered
	by `standard.html`

	:param doc: Document to be rendered.
	:param meta: Document meta object (doctype).
	:param format_data: Fields sequence and properties defined by Print Format Builder."""
	layout, page = [], []
	layout.append(page)

	def get_new_section():
		return {"columns": [], "has_data": False}

	def append_empty_field_dict_to_page_column(page):
		"""append empty columns dict to page layout"""
		if not page[-1]["columns"]:
			page[-1]["columns"].append({"fields": []})

	for df in format_data or meta.fields:
		if format_data:
			# embellish df with original properties
			df = frappe._dict(df)
			if df.fieldname:
				original = meta.get_field(df.fieldname)
				if original:
					newdf = original.as_dict()
					newdf.hide_in_print_layout = original.get("hide_in_print_layout")
					newdf.update(df)
					df = newdf

			df.print_hide = 0

		if df.fieldtype == "Section Break" or page == []:
			if len(page) > 1:
				if not page[-1]["has_data"]:
					# truncate last section if empty
					del page[-1]

			section = get_new_section()
			if df.fieldtype == "Section Break" and df.label:
				section["label"] = df.label

			page.append(section)

		elif df.fieldtype == "Column Break":
			# if last column break and last column is not empty
			page[-1]["columns"].append({"fields": []})

		else:
			# add a column if not yet added
			append_empty_field_dict_to_page_column(page)

		if df.fieldtype == "HTML" and df.options:
			doc.set(df.fieldname, True)  # show this field

		if df.fieldtype == "Signature" and not doc.get(df.fieldname):
			placeholder_image = "/assets/frappe/images/signature-placeholder.png"
			doc.set(df.fieldname, placeholder_image)

		if is_visible(df, doc) and has_value(df, doc):
			append_empty_field_dict_to_page_column(page)

			page[-1]["columns"][-1]["fields"].append(df)

			# section has fields
			page[-1]["has_data"] = True

			# if table, add the row info in the field
			# if a page break is found, create a new docfield
			if df.fieldtype == "Table":
				df.rows = []
				df.start = 0
				df.end = None
				for i, row in enumerate(doc.get(df.fieldname)):
					if row.get("page_break"):
						# close the earlier row
						df.end = i

						# new page, with empty section and column
						page = [get_new_section()]
						layout.append(page)
						append_empty_field_dict_to_page_column(page)

						# continue the table in a new page
						df = copy.copy(df)
						df.start = i
						df.end = None
						page[-1]["columns"][-1]["fields"].append(df)

	return layout


def is_visible(df: "DocField", doc: "Document") -> bool:
	"""Return True if docfield is visible in print layout and does not have print_hide set."""
	if df.fieldtype in ("Section Break", "Column Break", "Button"):
		return False

	if (df.permlevel or 0) > 0 and not doc.has_permlevel_access_to(df.fieldname, df):
		return False

	return not doc.is_print_hide(df.fieldname, df)


def has_value(df: "DocField", doc: "Document") -> bool:
	"""Return True if given docfield (`df`) has some value in the given document (`doc`)."""
	value = doc.get(df.fieldname)
	if value in (None, ""):
		return False

	elif isinstance(value, str) and not strip_html(value).strip():
		if df.fieldtype in ["Text", "Text Editor"]:
			return True

		return False

	elif isinstance(value, list) and not len(value):
		return False

	return True


def get_print_style(
	style: str | None = None, print_format: Optional["PrintFormat"] = None, for_legacy: bool = False
) -> str:
	print_settings = frappe.get_doc("Print Settings")

	if not style:
		style = print_settings.print_style or ""

	context = {
		"print_settings": print_settings,
		"print_style": style,
		"font": get_font(print_settings, print_format, for_legacy),
	}

	css = frappe.get_template("templates/styles/standard.css").render(context)

	if style and frappe.db.exists("Print Style", style):
		css = css + "\n" + frappe.db.get_value("Print Style", style, "css")

	# move @import to top
	for at_import in list(set(re.findall(r"(@import url\([^\)]+\)[;]?)", css))):
		css = css.replace(at_import, "")

		# prepend css with at_import
		css = at_import + css

	if print_format and print_format.css:
		css += "\n\n" + print_format.css

	return css


def get_font(
	print_settings: "PrintSettings", print_format: Optional["PrintFormat"] = None, for_legacy=False
) -> str:
	default = """
	"InterVariable", "Inter", -apple-system", "BlinkMacSystemFont",
		"Segoe UI", "Roboto", "Oxygen", "Ubuntu", "Cantarell", "Fira Sans", "Droid Sans",
		"Helvetica Neue", sans-serif;
	"""
	if for_legacy:
		return default

	font = None
	if print_format:
		if print_format.font and print_format.font != "Default":
			font = f"{print_format.font}, sans-serif"

	if not font:
		if print_settings.font and print_settings.font != "Default":
			font = f"{print_settings.font}, sans-serif"

		else:
			font = default

	return font


def get_visible_columns(data: list, table_meta: "Meta", df: "DocField") -> list["DocField"]:
	"""Return list of visible columns based on print_hide and if all columns have value."""
	columns = []
	doc = data[0] or frappe.new_doc(df.options)

	hide_in_print_layout = df.get("hide_in_print_layout") or []

	def add_column(col_df: "DocField"):
		if col_df.fieldname in hide_in_print_layout:
			return False
		return is_visible(col_df, doc) and column_has_value(data, col_df.get("fieldname"), col_df)

	if df.get("visible_columns"):
		# columns specified by column builder
		for col_df in df.get("visible_columns"):
			# load default docfield properties
			docfield = table_meta.get_field(col_df.get("fieldname"))
			if not docfield:
				continue
			newdf = docfield.as_dict().copy()
			newdf.update(col_df)
			if add_column(newdf):
				columns.append(newdf)
	else:
		for col_df in table_meta.fields:
			if add_column(col_df):
				columns.append(col_df)

	return columns


def column_has_value(data: list, fieldname: str, col_df: "DocField") -> bool:
	"""Check if at least one cell in column has non-zero and non-blank value"""
	has_value = False

	if col_df.fieldtype in ["Float", "Currency"] and not col_df.print_hide_if_no_value:
		return True

	for row in data:
		value = row.get(fieldname)
		if value:
			if isinstance(value, str):
				if strip_html(value).strip():
					has_value = True
					break
			else:
				has_value = True
				break

	return has_value


trigger_print_script = """
<script>
//allow wrapping of long tr
var elements = document.getElementsByTagName("tr");
var i = elements.length;
while (i--) {
	if(elements[i].clientHeight>300){
		elements[i].setAttribute("style", "page-break-inside: auto;");
	}
}

window.print();

// close the window after print
// NOTE: doesn't close if print is cancelled in Chrome
// Changed timeout to 5s from 1s because it blocked mobile view rendering
setTimeout(function() {
	window.close();
}, 5000);
</script>
"""
