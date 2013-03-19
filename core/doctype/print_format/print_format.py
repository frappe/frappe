# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 

from __future__ import unicode_literals
import webnotes, conf, os
from webnotes.utils import get_base_path

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
		if self.doc.standard == 'Yes' and getattr(conf, 'developer_mode', 0) == 1:
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
		
	obj = webnotes.get_obj(webnotes.form_dict.doctype, webnotes.form_dict.name)
	return {
		"body": get_html(obj.doc, obj.doclist)
	}

def get_html(doc, doclist):
	from jinja2 import Environment
	from core.doctype.print_style.print_style import get_print_style
	from core.doctype.print_format.print_format import get_print_format

	template = Environment().from_string(get_print_format(webnotes.form_dict.format))
	doctype = webnotes.get_doctype(doc.doctype)
	
	args = {
		"doc": doc,
		"doclist": doclist,
		"print_style": get_print_style(),
		"doctype_structure": make_doctype_structure(doctype),
		"doctype": doctype
	}
	html = template.render(args)
	return html

def make_doctype_structure(doctype):
	s = []
	fields = doctype.get({"doctype":"DocField"})
		
	# first get all section breaks
	for docfield in fields:
		if docfield.fieldtype=="Section Break":
			s.append(docfield)
	
	if s[0].idx != 1:
		s = [webnotes._dict({"fieldtype":"Section Break", "idx":-1})] + s
		
	# then get columns in inside section break
	for sb in s:
		sb.columns = []
				
		for docfield in fields:
			if docfield.idx > sb.idx:
				# missing first column break
				if docfield.idx == sb.idx + 1 and docfield.fieldtype!="Column Break":
					sb.columns.append(webnotes._dict({"fieldtype":"Column Break", 
						"idx":sb.idx}))
				elif docfield.fieldtype=="Column Break":
					sb.columns.append(docfield)
				elif docfield.fieldtype=="Section Break":
					break
					
		for cb in sb.columns:
			cb.fields = []

	return s

def get_print_format(name):
	html = webnotes.conn.get_value("Print Format", name, "html")
	if html: 
		return html

	# server, find template
	path = os.path.join(get_base_path(), "lib", "core", "doctype", "print_format", 
		"templates", name.lower() + ".html")
	if os.path.exists(path):
		with open(path, "r") as pffile:
			return pffile.read()
	else:
		return ""

