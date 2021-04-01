# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe


def execute():
	frappe.reload_doc("website", "doctype", "web_page_block")
	# remove unused templates
	frappe.delete_doc("Web Template", "Navbar with Links on Right", force=1)
	frappe.delete_doc("Web Template", "Footer Horizontal", force=1)

