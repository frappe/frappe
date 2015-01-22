# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe, os, copy, json, re
from frappe import _

from frappe.modules import get_doc_path
from jinja2 import TemplateNotFound
from frappe.utils import cint, strip_html
from frappe.utils.pdf import get_pdf

no_cache = 1
no_sitemap = 1

base_template_path = "templates/pages/print.html"
standard_format = "templates/print_formats/standard.html"

def get_context(context):
	if not frappe.form_dict.format:
		frappe.form_dict.format = standard_format

	if not frappe.form_dict.doctype or not frappe.form_dict.name:
		return {
			"body": """<h1>Error</h1>
				<p>Parameters doctype, name and format required</p>
				<pre>%s</pre>""" % repr(frappe.form_dict)
		}

	doc = frappe.get_doc(frappe.form_dict.doctype, frappe.form_dict.name)
	meta = frappe.get_meta(doc.doctype)

	return {
		"body": get_html(doc, print_format = frappe.form_dict.format,
			meta=meta, trigger_print = frappe.form_dict.trigger_print, no_letterhead=frappe.form_dict.no_letterhead),
		"css": get_print_style(frappe.form_dict.style),
		"comment": frappe.session.user,
		"title": doc.get(meta.title_field) if meta.title_field else doc.name
	}

@frappe.whitelist()
def get_html(doc, name=None, print_format=None, meta=None,
	no_letterhead=None, trigger_print=False):

	if isinstance(no_letterhead, basestring):
		no_letterhead = cint(no_letterhead)
	elif no_letterhead is None:
		no_letterhead = not cint(frappe.db.get_single_value("Print Settings", "with_letterhead"))

	if isinstance(doc, basestring) and isinstance(name, basestring):
		doc = frappe.get_doc(doc, name)

	if isinstance(doc, basestring):
		doc = frappe.get_doc(json.loads(doc))

	doc.in_print = True

	validate_print_permission(doc)

	if hasattr(doc, "before_print"):
		doc.before_print()

	if not hasattr(doc, "print_heading"): doc.print_heading = None
	if not hasattr(doc, "sub_heading"): doc.sub_heading = None

	if not meta:
		meta = frappe.get_meta(doc.doctype)

	jenv = frappe.get_jenv()
	if print_format in ("Standard", standard_format):
		template = jenv.get_template("templates/print_formats/standard.html")
	else:
		template = jenv.from_string(get_print_format(doc.doctype,
			print_format))

	args = {
		"doc": doc,
		"meta": frappe.get_meta(doc.doctype),
		"layout": make_layout(doc, meta),
		"no_letterhead": no_letterhead,
		"trigger_print": cint(trigger_print),
		"letter_head": get_letter_head(doc, no_letterhead)
	}

	html = template.render(args, filters={"len": len})

	return html

@frappe.whitelist()
def download_pdf(doctype, name, format=None):
	html = frappe.get_print_format(doctype, name, format)
	frappe.local.response.filename = "{name}.pdf".format(name=name.replace(" ", "-").replace("/", "-"))
	frappe.local.response.filecontent = get_pdf(html)
	frappe.local.response.type = "download"

def validate_print_permission(doc):
	for ptype in ("read", "print"):
		if not frappe.has_permission(doc.doctype, ptype, doc):
			raise frappe.PermissionError(_("No {0} permission").format(ptype))

def get_letter_head(doc, no_letterhead):
	if no_letterhead:
		return ""
	if doc.get("letter_head"):
		return frappe.db.get_value("Letter Head", doc.letter_head, "content")
	else:
		return frappe.db.get_value("Letter Head", {"is_default": 1}, "content") or ""

def get_print_format(doctype, format_name):
	if format_name==standard_format:
		return format_name

	opts = frappe.db.get_value("Print Format", format_name, "disabled", as_dict=True)
	if not opts:
		frappe.throw(_("Print Format {0} does not exist").format(format_name), frappe.DoesNotExistError)
	elif opts.disabled:
		frappe.throw(_("Print Format {0} is disabled").format(format_name), frappe.DoesNotExistError)

	# server, find template
	path = os.path.join(get_doc_path(frappe.db.get_value("DocType", doctype, "module"),
		"Print Format", format_name), frappe.scrub(format_name) + ".html")

	if os.path.exists(path):
		with open(path, "r") as pffile:
			return pffile.read()
	else:
		html = frappe.db.get_value("Print Format", format_name, "html")
		if html:
			return html
		else:
			frappe.throw(_("No template found at path: {0}").format(path),
				frappe.TemplateNotFoundError)

def make_layout(doc, meta):
	layout, page = [], []
	layout.append(page)
	for df in meta.fields:
		if df.fieldtype=="Section Break" or page==[]:
			page.append([])

		if df.fieldtype=="Column Break" or (page[-1]==[] and df.fieldtype!="Section Break"):
			page[-1].append([])

		if df.fieldtype=="HTML" and df.options:
			doc.set(df.fieldname, True) # show this field

		if is_visible(df) and has_value(df, doc):
			page[-1][-1].append(df)

			# if table, add the row info in the field
			# if a page break is found, create a new docfield
			if df.fieldtype=="Table":
				df.rows = []
				df.start = 0
				df.end = None
				for i, row in enumerate(doc.get(df.fieldname)):
					if row.get("page_break"):
						# close the earlier row
						df.end = i

						# new page, with empty section and column
						page = [[[]]]
						layout.append(page)

						# continue the table in a new page
						df = copy.copy(df)
						df.start = i
						df.end = None
						page[-1][-1].append(df)

	# filter empty sections
	layout = [filter(lambda s: any(filter(lambda c: any(c), s)), page) for page in layout]
	return layout

def is_visible(df):
	no_display = ("Section Break", "Column Break", "Button")
	return (df.fieldtype not in no_display) and not df.get("__print_hide") and not df.print_hide

def has_value(df, doc):
	value = doc.get(df.fieldname)
	if value in (None, ""):
		return False

	elif isinstance(value, basestring) and not strip_html(value).strip():
		return False

	return True

def get_print_style(style=None):
	print_settings = frappe.get_doc("Print Settings")

	if not style:
		style = print_settings.print_style or "Standard"

	context = {"print_settings": print_settings, "print_style": style}

	css = frappe.get_template("templates/styles/standard.css").render(context)

	try:
		additional_css = frappe.get_template("templates/styles/" + style.lower() + ".css").render(context)

		# move @import to top
		for at_import in list(set(re.findall("(@import url\([^\)]+\)[;]?)", additional_css))):
			additional_css = additional_css.replace(at_import, "")

			# prepend css with at_import
			css = at_import + css

		css += "\n" + additional_css
	except TemplateNotFound:
		pass

	return css

def get_visible_columns(data, table_meta):
	columns = []
	for tdf in table_meta.fields:
		if is_visible(tdf) and column_has_value(data, tdf.fieldname):
			columns.append(tdf)

	return columns

def column_has_value(data, fieldname):
	"""Check if at least one cell in column has non-zero and non-blank value"""
	has_value = False

	for row in data:
		value = row.get(fieldname)
		if value:
			if isinstance(value, basestring):
				if strip_html(value).strip():
					has_value = True
					break
			else:
				has_value = True
				break

	return has_value

