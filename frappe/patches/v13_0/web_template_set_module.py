# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	"""Set default module for standard Web Template, if none."""
	frappe.reload_doctype('Web Template')
	frappe.reload_doctype('Web Template Field')
	standard_templates = frappe.get_list('Web Template', {'standard': 1})
	for template in standard_templates:
		doc = frappe.get_doc('Web Template', template.name)
		if not doc.module:
			doc.module = 'Website'
			doc.save()
