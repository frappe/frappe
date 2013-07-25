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

from __future__ import unicode_literals
import webnotes

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def validate(self):
		self.set_active()
		self.create_custom_field_for_workflow_state()
		self.update_default_workflow_status()
		
	def on_update(self):
		webnotes.clear_cache(doctype=self.doc.document_type)
	
	def create_custom_field_for_workflow_state(self):
		webnotes.clear_cache(doctype=self.doc.document_type)
		doctypeobj = webnotes.get_doctype(self.doc.document_type)
		if not len(doctypeobj.get({"doctype":"DocField", 
			"fieldname":self.doc.workflow_state_field})):
			
			# create custom field
			webnotes.bean([{
				"doctype":"Custom Field",
				"dt": self.doc.document_type,
				"__islocal": 1,
				"fieldname": self.doc.workflow_state_field,
				"label": self.doc.workflow_state_field.replace("_", " ").title(),
				"hidden": 1,
				"fieldtype": "Link",
				"options": "Workflow State",
				#"insert_after": doctypeobj.get({"doctype":"DocField"})[-1].fieldname
			}]).save()
			
			webnotes.msgprint("Created Custom Field '%s' in '%s'" % (self.doc.workflow_state_field,
				self.doc.document_type))

	def update_default_workflow_status(self):
		docstatus_map = {}
		states = self.doclist.get({"doctype": "Workflow Document State"})
		states.sort(lambda x, y: x.idx - y.idx)
		for d in self.doclist.get({"doctype": "Workflow Document State"}):
			if not d.doc_status in docstatus_map:
				webnotes.conn.sql("""update `tab%s` set `%s` = %s where \
					ifnull(`%s`, '')='' and docstatus=%s""" % (self.doc.document_type, self.doc.workflow_state_field,
						'%s', self.doc.workflow_state_field, "%s"), (d.state, d.doc_status))
				docstatus_map[d.doc_status] = d.state
		
	def set_active(self):
		if int(self.doc.is_active or 0):
			# clear all other
			webnotes.conn.sql("""update tabWorkflow set is_active=0 
				where document_type=%s""",
				self.doc.document_type)
