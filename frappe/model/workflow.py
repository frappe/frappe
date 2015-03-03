# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def get_workflow_name(doctype):
	if getattr(frappe.local, "workflow_names", None) is None:
		frappe.local.workflow_names = {}

	if doctype not in frappe.local.workflow_names:
		workflow_name = frappe.db.get_value("Workflow", {"document_type": doctype,
			"is_active": 1}, "name")

		frappe.local.workflow_names[doctype] = workflow_name

	return frappe.local.workflow_names[doctype]

def get_default_state(doctype):
	workflow_name = get_workflow_name(doctype)
	return frappe.db.get_value("Workflow Document State", {"parent": workflow_name,
		"idx":1}, "state")

def get_state_fieldname(doctype):
	workflow_name = get_workflow_name(doctype)
	return frappe.db.get_value("Workflow", workflow_name, "workflow_state_field")
