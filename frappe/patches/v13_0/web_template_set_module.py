# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


def execute() -> None:
	"""Set default module for standard Web Template, if none."""
	frappe.reload_doc("website", "doctype", "Web Template Field")
	frappe.reload_doc("website", "doctype", "web_template")

	standard_templates = frappe.get_list("Web Template", {"standard": 1})
	for template in standard_templates:
		doc = frappe.get_doc("Web Template", template.name)
		if not doc.module:
			doc.module = "Website"
			doc.save()
