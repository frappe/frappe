# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.model.document import Document

class SessionDefaultSettings(Document):
	pass

@frappe.whitelist()
def get_session_default_values():
	settings = frappe.get_single('Session Default Settings')
	fields = []
	for default_values in settings.session_defaults:
		reference_doctype = frappe.scrub(default_values.ref_doctype)
		fields.append({
			'fieldname': reference_doctype,
			'fieldtype': 'Link',
			'options': default_values.ref_doctype,
			'label': 'Default ' + default_values.ref_doctype,
			'default': frappe.defaults.get_user_default(reference_doctype)
		})
	return json.dumps(fields)

@frappe.whitelist()
def set_session_default_values(default_values):
	default_values = json.loads(default_values)
	for entry in default_values:
		try:
			frappe.defaults.set_user_default(entry, default_values.get(entry))
		except:
			return
	return "success"

#called on hook 'on_logout' to clear defaults for the session
def clear_session_defaults():
	settings = frappe.get_single('Session Default Settings').session_defaults
	for entry in settings:
		document_type = frappe.db.get_value('Session Default', entry.name, 'ref_doctype')
		frappe.defaults.clear_user_default(frappe.scrub(document_type
		))
