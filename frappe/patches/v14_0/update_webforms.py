# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt


import frappe


def execute():
	frappe.reload_doc("website", "doctype", "web_form_list_column")
	frappe.reload_doctype("Web Form")

	for web_form in frappe.get_all("Web Form", fields=["*"]):
		if web_form.allow_multiple and not web_form.show_list:
			frappe.db.set_value("Web Form", web_form.name, "show_list", True)
