# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.model import rename_field
from frappe.modules import scrub, get_doctype_module

rename_map = {
	"Customize Form": [
		["customize_form_fields", "fields"]
	],
	"Email Alert": [
		["email_alert_recipients", "recipients"]
	],
	"Event": [
		["event_roles", "roles"]
	],
	"Workflow": [
		["workflow_document_states", "states"],
		["workflow_transitions", "transitions"]
	]
}

def execute():
	for dn in rename_map:
		frappe.reload_doc(get_doctype_module(dn), "doctype", scrub(dn))

	for dt, field_list in rename_map.items():
		for field in field_list:
			rename_field(dt, field[0], field[1])
