# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe

def execute():
	frappe.reload_doc("website", "doctype", "website_template")
	frappe.reload_doc("website", "doctype", "website_route")
	frappe.reload_doc("website", "doctype", "website_route_permission")
	frappe.reload_doc("website", "doctype", "website_group")
	frappe.reload_doc("website", "doctype", "post")
	frappe.reload_doc("website", "doctype", "user_vote")
	
	frappe.db.sql("""update `tabWebsite Route` ws set ref_doctype=(select wsc.ref_doctype
		from `tabWebsite Template` wsc where wsc.name=ws.website_template)
		where ifnull(page_or_generator, '')!='Page'""")
	
	frappe.reload_doc("website", "doctype", "website_settings")
	home_page = frappe.db.get_value("Website Settings", "Website Settings", "home_page")
	home_page = frappe.db.get_value("Website Route", {"docname": home_page}) or home_page
	frappe.db.set_value("Website Settings", "Website Settings", "home_page",
		home_page)
