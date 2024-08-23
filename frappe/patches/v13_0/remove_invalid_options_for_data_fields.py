# Copyright (c) 2022, Frappe and Contributors
# License: MIT. See LICENSE


import frappe
from frappe.model import data_field_options


def execute():
	custom_field = frappe.qb.DocType("Custom Field")
	(
		frappe.qb.update(custom_field)
		.set(custom_field.options, None)
		.where((custom_field.fieldtype == "Data") & (custom_field.options.notin(data_field_options)))
	).run()
