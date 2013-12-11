# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

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
