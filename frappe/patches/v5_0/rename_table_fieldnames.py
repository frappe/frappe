# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.model.utils.rename_field import rename_field
from frappe.modules import scrub, get_doctype_module

rename_map = {
	"Customize Form": [
		["customize_form_fields", "fields"]
	],
	"Email Alert": [
		["email_alert_recipients", "recipients"]
	],
	"Workflow": [
		["workflow_document_states", "states"],
		["workflow_transitions", "transitions"]
	]
}

def execute():
	frappe.reload_doc("custom", "doctype", "customize_form")
	frappe.reload_doc("email", "doctype", "email_alert")
	frappe.reload_doc("desk", "doctype", "event")
	frappe.reload_doc("workflow", "doctype", "workflow")

	for dt, field_list in rename_map.items():
		for field in field_list:
			rename_field(dt, field[0], field[1])
