# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	"""Set default module for standard Web Template, if none."""
<<<<<<< d5ee3032d494ed35a409a36116679a3d3cb96103
	frappe.reload_doc('website', 'doctype', 'Web Template Field')
	frappe.reload_doc('website', 'doctype', 'web_template')

=======
	frappe.reload_doc('website', 'doctype', 'Web Template')
	frappe.reload_doc('website', 'doctype', 'Web Template Field')
>>>>>>> fix(minor): fix fieldame in apply_property_setters in model/meta.py
	standard_templates = frappe.get_list('Web Template', {'standard': 1})
	for template in standard_templates:
		doc = frappe.get_doc('Web Template', template.name)
		if not doc.module:
			doc.module = 'Website'
			doc.save()
