# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe, os, copy, json, re
from frappe import _

from frappe.modules import get_doc_path
from frappe.utils import cint, strip_html
from markdown2 import markdown
from six import string_types

no_cache = 1
no_sitemap = 1

base_template_path = "templates/www/printview.html"
standard_format = "templates/print_formats/standard.html"

def get_context(context):
	"""Build context for print"""
	if not ((frappe.form_dict.doctype and frappe.form_dict.name) or frappe.form_dict.doc):
		return {
			"body": """<h1>Error</h1>
				<p>Parameters doctype and name required</p>
				<pre>%s</pre>""" % repr(frappe.form_dict)
		}

	if frappe.form_dict.doc:
		doc = frappe.form_dict.doc
	else:
		doc = frappe.get_doc(frappe.form_dict.doctype, frappe.form_dict.name)

	meta = frappe.get_meta(doc.doctype)

	print_format = get_print_format_doc(None, meta = meta)

	return {
		"body": get_html(doc, print_format = print_format,
			meta=meta, trigger_print = frappe.form_dict.trigger_print,
			no_letterhead=frappe.form_dict.no_letterhead),
		"css": get_print_style(frappe.form_dict.style, print_format),
		"comment": frappe.session.user,
		"title": doc.get(meta.title_field) if meta.title_field else doc.name
	}

def get_print_format_doc(print_format_name, meta):
	"""Returns print format document"""
	if not print_format_name:
		print_format_name = frappe.form_dict.format \
			or meta.default_print_format or "Standard"

	if print_format_name == "Standard":
		return None
	else:
		try:
			return frappe.get_doc("Print Format", print_format_name)
		except frappe.DoesNotExistError:
			# if old name, return standard!
			return None

def get_html(doc, name=None, print_format=None, meta=None,
	no_letterhead=None, trigger_print=False):

	print_settings = frappe.db.get_singles_dict("Print Settings")

	if isinstance(no_letterhead, string_types):
		no_letterhead = cint(no_letterhead)

	elif no_letterhead is None:
		no_letterhead = not cint(print_settings.with_letterhead)

	doc.flags.in_print = True

	if not frappe.flags.ignore_print_permissions:
		validate_print_permission(doc)

	if doc.meta.is_submittable:
		if doc.docstatus==0 and not cint(print_settings.allow_print_for_draft):
			frappe.throw(_("Not allowed to print draft documents"), frappe.PermissionError)

		if doc.docstatus==2 and not cint(print_settings.allow_print_for_cancelled):
			frappe.throw(_("Not allowed to print cancelled documents"), frappe.PermissionError)

	if hasattr(doc, "before_print"):
		doc.before_print()

	if not hasattr(doc, "print_heading"): doc.print_heading = None
	if not hasattr(doc, "sub_heading"): doc.sub_heading = None

	if not meta:
		meta = frappe.get_meta(doc.doctype)

	jenv = frappe.get_jenv()
	format_data, format_data_map = [], {}

	# determine template
	if print_format:
		doc._show_section_headings = print_format.show_section_headings
		doc._line_breaks = print_format.line_breaks
		doc._align_labels_right = print_format.align_labels_right

		def get_template_from_string():
			return jenv.from_string(get_print_format(doc.doctype,
				print_format))

		if print_format.custom_format:
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

		elif print_format.standard=="Yes":
			template = get_template_from_string()

		else:
			# fallback
			template = "standard"

	else:
		template = "standard"


	if template == "standard":
		template = jenv.get_template(standard_format)

	letter_head = frappe._dict(get_letter_head(doc, no_letterhead) or {})

	if letter_head.content:
		letter_head.content = frappe.utils.jinja.render_template(letter_head.content, {"doc": doc.as_dict()})

	if letter_head.footer:
		letter_head.footer = frappe.utils.jinja.render_template(letter_head.footer, {"doc": doc.as_dict()})

	convert_markdown(doc, meta)

	args = {
		"doc": doc,
		"meta": frappe.get_meta(doc.doctype),
		"layout": make_layout(doc, meta, format_data),
		"no_letterhead": no_letterhead,
		"trigger_print": cint(trigger_print),
		"letter_head": letter_head.content,
		"footer": letter_head.footer,
		"print_settings": frappe.get_doc("Print Settings")
	}

	html = template.render(args, filters={"len": len})

	if cint(trigger_print):
		html += trigger_print_script

	return html

def convert_markdown(doc, meta):
	'''Convert text field values to markdown if necessary'''
	for field in meta.fields:
		if field.fieldtype=='Text Editor':
			value = doc.get(field.fieldname)
			if value and '<!-- markdown -->' in value:
				doc.set(field.fieldname, markdown(value))

@frappe.whitelist()
def get_html_and_style(doc, name=None, print_format=None, meta=None,
	no_letterhead=None, trigger_print=False, style=None):
	"""Returns `html` and `style` of print format, used in PDF etc"""

	if isinstance(doc, string_types) and isinstance(name, string_types):
		doc = frappe.get_doc(doc, name)

	if isinstance(doc, string_types):
		doc = frappe.get_doc(json.loads(doc))

	print_format = get_print_format_doc(print_format, meta=meta or frappe.get_meta(doc.doctype))
	return {
		"html": get_html(doc, name=name, print_format=print_format, meta=meta,
	no_letterhead=no_letterhead, trigger_print=trigger_print),
		"style": get_print_style(style=style, print_format=print_format)
	}

def validate_print_permission(doc):
	if frappe.form_dict.get("key"):
		if frappe.form_dict.key == doc.get_signature():
			return

	for ptype in ("read", "print"):
		if (not frappe.has_permission(doc.doctype, ptype, doc)
			and not frappe.has_website_permission(doc)):
			raise frappe.PermissionError(_("No {0} permission").format(ptype))

def get_letter_head(doc, no_letterhead):
	if no_letterhead:
		return {}
	if doc.get("letter_head"):
		return frappe.db.get_value("Letter Head", doc.letter_head, ["content", "footer"], as_dict=True)
	else:
		return frappe.db.get_value("Letter Head", {"is_default": 1}, ["content", "footer"], as_dict=True) or {}

def get_print_format(doctype, print_format):
	if print_format.disabled:
		frappe.throw(_("Print Format {0} is disabled").format(print_format.name),
			frappe.DoesNotExistError)

	# server, find template
	path = os.path.join(get_doc_path(frappe.db.get_value("DocType", doctype, "module"),
		"Print Format", print_format.name), frappe.scrub(print_format.name) + ".html")

	if os.path.exists(path):
		with open(path, "r") as pffile:
			return pffile.read()
	else:
		if print_format.html:
			return print_format.html
		else:
			frappe.throw(_("No template found at path: {0}").format(path),
				frappe.TemplateNotFoundError)

def make_layout(doc, meta, format_data=None):
	"""Builds a hierarchical layout object from the fields list to be rendered
	by `standard.html`

	:param doc: Document to be rendered.
	:param meta: Document meta object (doctype).
	:param format_data: Fields sequence and properties defined by Print Format Builder."""
	layout, page = [], []
	layout.append(page)

	if format_data:
		# extract print_heading_template from the first field
		# and remove the field
		if format_data[0].get("fieldname") == "print_heading_template":
			doc.print_heading_template = format_data[0].get("options")
			format_data = format_data[1:]

	def get_new_section(): return  {'columns': [], 'has_data': False}

	def append_empty_field_dict_to_page_column(page):
		""" append empty columns dict to page layout """
		if not page[-1]['columns']:
			page[-1]['columns'].append({'fields': []})

	for df in format_data or meta.fields:
		if format_data:
			# embellish df with original properties
			df = frappe._dict(df)
			if df.fieldname:
				original = meta.get_field(df.fieldname)
				if original:
					newdf = original.as_dict()
					newdf.update(df)
					df = newdf

			df.print_hide = 0

		if df.fieldtype=="Section Break" or page==[]:
			if len(page) > 1:
				if page[-1]['has_data']==False:
					# truncate last section if empty
					del page[-1]

			section = get_new_section()
			if df.fieldtype=='Section Break' and df.label:
				section['label'] = df.label

			page.append(section)

		elif df.fieldtype=="Column Break":
			# if last column break and last column is not empty
			page[-1]['columns'].append({'fields': []})

		else:
			# add a column if not yet added
			append_empty_field_dict_to_page_column(page)

		if df.fieldtype=="HTML" and df.options:
			doc.set(df.fieldname, True) # show this field

		if is_visible(df, doc) and has_value(df, doc):
			append_empty_field_dict_to_page_column(page)

			page[-1]['columns'][-1]['fields'].append(df)

			# section has fields
			page[-1]['has_data'] = True

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
						page = [get_new_section()]
						layout.append(page)
						append_empty_field_dict_to_page_column(page)

						# continue the table in a new page
						df = copy.copy(df)
						df.start = i
						df.end = None
						page[-1]['columns'][-1]['fields'].append(df)

	return layout

def is_visible(df, doc):
	"""Returns True if docfield is visible in print layout and does not have print_hide set."""
	if df.fieldtype in ("Section Break", "Column Break", "Button"):
		return False

	if hasattr(doc, "hide_in_print_layout"):
		if df.fieldname in doc.hide_in_print_layout:
			return False

	if df.permlevel > 0 and not doc.has_permlevel_access_to(df.fieldname, df):
		return False

	return not doc.is_print_hide(df.fieldname, df)

def has_value(df, doc):
	value = doc.get(df.fieldname)
	if value in (None, ""):
		return False

	elif isinstance(value, string_types) and not strip_html(value).strip():
		return False

	elif isinstance(value, list) and not len(value):
		return False

	return True

def get_print_style(style=None, print_format=None, for_legacy=False):
	print_settings = frappe.get_doc("Print Settings")

	if not style:
		style = print_settings.print_style or ''

	context = {
		"print_settings": print_settings,
		"print_style": style,
		"font": get_font(print_settings, print_format, for_legacy)
	}

	css = frappe.get_template("templates/styles/standard.css").render(context)

	if style and frappe.db.exists('Print Style', style):
		css = css + '\n' + frappe.db.get_value('Print Style', style, 'css')

	# move @import to top
	for at_import in list(set(re.findall("(@import url\([^\)]+\)[;]?)", css))):
		css = css.replace(at_import, "")

		# prepend css with at_import
		css = at_import + css

	if print_format and print_format.css:
		css += "\n\n" + print_format.css

	return css

def get_font(print_settings, print_format=None, for_legacy=False):
	default = '"Helvetica Neue", Helvetica, Arial, "Open Sans", sans-serif'
	if for_legacy:
		return default

	font = None
	if print_format:
		if print_format.font and print_format.font!="Default":
			font = '{0}, sans-serif'.format(print_format.font)

	if not font:
		if print_settings.font and print_settings.font!="Default":
			font = '{0}, sans-serif'.format(print_settings.font)

		else:
			font = default

	return font

def get_visible_columns(data, table_meta, df):
	"""Returns list of visible columns based on print_hide and if all columns have value."""
	columns = []
	doc = data[0] or frappe.new_doc(df.options)
	def add_column(col_df):
		return is_visible(col_df, doc) \
			and column_has_value(data, col_df.get("fieldname"))

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

def column_has_value(data, fieldname):
	"""Check if at least one cell in column has non-zero and non-blank value"""
	has_value = False

	for row in data:
		value = row.get(fieldname)
		if value:
			if isinstance(value, string_types):
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
setTimeout(function() {
	window.close();
}, 1000);
</script>
"""
