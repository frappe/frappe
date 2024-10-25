# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


def execute() -> None:
	frappe.reload_doc("website", "doctype", "web_page_block")
	# remove unused templates
	frappe.delete_doc("Web Template", "Navbar with Links on Right", force=1)
	frappe.delete_doc("Web Template", "Footer Horizontal", force=1)
