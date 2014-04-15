# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, os
import frappe.utils
from frappe.modules import get_doc_path

standard_format = "templates/print_formats/standard.html"

from frappe.model.document import Document

class PrintFormat(Document):
	def validate(self):
		if self.standard=="Yes" and frappe.session.user != "Administrator":
			frappe.throw(frappe._("Standard Print Format cannot be updated"))

		# old_doc_type is required for clearing item cache
		self.old_doc_type = frappe.db.get_value('Print Format',
				self.name, 'doc_type')

	def on_update(self):
		if hasattr(self, 'old_doc_type') and self.old_doc_type:
			frappe.clear_cache(doctype=self.old_doc_type)
		if self.doc_type:
			frappe.clear_cache(doctype=self.doc_type)

		self.export_doc()

	def export_doc(self):
		# export
		if self.standard == 'Yes' and (frappe.conf.get('developer_mode') or 0) == 1:
			from frappe.modules.export_file import export_to_files
			export_to_files(record_list=[['Print Format', self.name]],
				record_module=self.module)

	def on_trash(self):
		if self.doc_type:
			frappe.clear_cache(doctype=self.doc_type)

def get_args():
	if not frappe.form_dict.format:
		frappe.form_dict.format = standard_format
	if not frappe.form_dict.doctype or not frappe.form_dict.name:
		return {
			"body": """<h1>Error</h1>
				<p>Parameters doctype, name and format required</p>
				<pre>%s</pre>""" % repr(frappe.form_dict)
		}

	doc = frappe.get_doc(frappe.form_dict.doctype, frappe.form_dict.name)
	for ptype in ("read", "print"):
		if not frappe.has_permission(doc.doctype, ptype, doc):
			return {
				"body": """<h1>Error</h1>
					<p>No {ptype} permission</p>""".format(ptype=ptype)
			}

	return {
		"body": get_html(doc),
		"css": get_print_style(frappe.form_dict.style),
		"comment": frappe.session.user
	}

def get_html(doc, name=None, print_format=None):
	from jinja2 import Environment

	if isinstance(doc, basestring) and isinstance(name, basestring):
		doc = frappe.get_doc(doc, name)

	template = Environment().from_string(get_print_format_name(doc.doctype,
		print_format or frappe.form_dict.format))
	meta = frappe.get_meta(doc.doctype)

	args = {
		"doc": doc,
		"meta": meta,
		"frappe": frappe,
		"utils": frappe.utils
	}
	html = template.render(args)
	return html

def get_print_format_name(doctype, format_name):
	if format_name==standard_format:
		return format_name

	# server, find template
	path = os.path.join(get_doc_path(frappe.db.get_value("DocType", doctype, "module"),
		"Print Format", format_name), format_name + ".html")
	if os.path.exists(path):
		with open(path, "r") as pffile:
			return pffile.read()
	else:
		html = frappe.db.get_value("Print Format", format_name, "html")
		if html:
			return html
		else:
			return "No template found.\npath: " + path

def get_print_style(style=None):
	if not style:
		style = frappe.db.get_default("print_style") or "Standard"
	path = os.path.join(get_doc_path("Core", "DocType", "Print Format"), "styles",
		style.lower() + ".css")
	if not os.path.exists(path):
		if style!="Standard":
			return get_print_style("Standard")
		else:
			return "/* Standard Style Missing ?? */"
	else:
		with open(path, 'r') as sfile:
			return sfile.read()
