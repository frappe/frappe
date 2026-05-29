# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.doctypes import WebTemplate


def execute():
	"""Set default module for standard Web Template, if none."""
	frappe.reload_doc("website", "doctype", "Web Template Field")
	frappe.reload_doc("website", "doctype", "web_template")

	standard_templates = frappe.get_list("Web Template", {"standard": 1})
	for template in standard_templates:
		doc = WebTemplate.docs.get(template.name)
		if not doc.module:
			doc.module = "Website"
			doc.save()
