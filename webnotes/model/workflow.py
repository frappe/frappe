# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes

def get_workflow_name(doctype):
	if getattr(webnotes.local, "workflow_names", None) is None:
		webnotes.local.workflow_names = {}
	
	if doctype not in webnotes.local.workflow_names:
		workflow_name = webnotes.conn.get_value("Workflow", {"document_type": doctype, 
			"is_active": "1"}, "name")
	
		# no active? get default workflow
		if not workflow_name:
			workflow_name = webnotes.conn.get_value("Workflow", {"document_type": doctype}, 
			"name")
				
		webnotes.local.workflow_names[doctype] = workflow_name
			
	return webnotes.local.workflow_names[doctype]
	
def get_default_state(doctype):
	workflow_name = get_workflow_name(doctype)
	return webnotes.conn.get_value("Workflow Document State", {"parent": workflow_name,
		"idx":1}, "state")
		
def get_state_fieldname(doctype):
	workflow_name = get_workflow_name(doctype)
	return webnotes.conn.get_value("Workflow", workflow_name, "workflow_state_field")
