# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import webnotes, os
from webnotes import conf
import webnotes.utils
from webnotes.utils import get_base_path
from webnotes.modules import get_doc_path

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d,dl

	def validate(self):
		if self.doc.standard=="Yes" and webnotes.session.user != "Administrator":
			webnotes.msgprint("Standard Print Format cannot be updated.", raise_exception=1)
		
		# old_doc_type is required for clearing item cache
		self.old_doc_type = webnotes.conn.get_value('Print Format',
				self.doc.name, 'doc_type')

	def on_update(self):
		if hasattr(self, 'old_doc_type') and self.old_doc_type:
			webnotes.clear_cache(doctype=self.old_doc_type)		
		if self.doc.doc_type:
			webnotes.clear_cache(doctype=self.doc.doc_type)

		self.export_doc()
	
	def export_doc(self):
		# export
		if self.doc.standard == 'Yes' and (conf.get('developer_mode') or 0) == 1:
			from webnotes.modules.export_file import export_to_files
			export_to_files(record_list=[['Print Format', self.doc.name]], 
				record_module=self.doc.module)	
	
	def on_trash(self):
		if self.doc.doc_type:
			webnotes.clear_cache(doctype=self.doc.doc_type)

def get_args():
	if not webnotes.form_dict.doctype or not webnotes.form_dict.name \
		or not webnotes.form_dict.format:
		return {
			"body": """<h1>Error</h1>
				<p>Parameters doctype, name and format required</p>
				<pre>%s</pre>""" % repr(webnotes.form_dict)
		}
		
	bean = webnotes.bean(webnotes.form_dict.doctype, webnotes.form_dict.name)
	if not bean.has_read_perm():
		return {
			"body": """<h1>Error</h1>
				<p>No read permission</p>"""
		}
	
	return {
		"body": get_html(bean.doc, bean.doclist),
		"css": get_print_style(webnotes.form_dict.style),
		"comment": webnotes.session.user
	}

def get_html(doc, doclist):
	from jinja2 import Environment
	from webnotes.core.doctype.print_format.print_format import get_print_format

	template = Environment().from_string(get_print_format(doc.doctype, 
		webnotes.form_dict.format))
	doctype = webnotes.get_doctype(doc.doctype)
	
	args = {
		"doc": doc,
		"doclist": doclist,
		"doctype": doctype,
		"webnotes": webnotes,
		"utils": webnotes.utils
	}
	html = template.render(args)
	return html

def get_print_format(doctype, format):
	# server, find template
	path = os.path.join(get_doc_path(webnotes.conn.get_value("DocType", doctype, "module"), 
		"Print Format", format), format + ".html")
	if os.path.exists(path):
		with open(path, "r") as pffile:
			return pffile.read()
	else:
		html = webnotes.conn.get_value("Print Format", format, "html")
		if html:
			return html
		else:
			return "No template found.\npath: " + path

def get_print_style(style=None):
	if not style:
		style = webnotes.conn.get_default("print_style") or "Standard"
	path = os.path.join(get_doc_path("Core", "DocType", "Print Format"), "styles", 
		style.lower() + ".css")
	if not os.path.exists(path):
		if style!="Standard":
			return get_print_style("Standard")
		else:
			return "/* Standard Style Missing ?? */"
	else:
		with open(path, 'r') as sfile:
			return sfile.read() + """ \* test *\ """
	