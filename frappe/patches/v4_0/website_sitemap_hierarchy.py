# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe

def execute():
	# frappe.db.sql("""update `tabWebsite Route` ws set ref_doctype=(select wsc.ref_doctype
	# 	from `tabWebsite Template` wsc where wsc.name=ws.website_template)
	# 	where ifnull(page_or_generator, '')!='Page'""")

	frappe.reload_doc("website", "doctype", "website_settings")

	# original_home_page = frappe.db.get_value("Website Settings", "Website Settings", "home_page")
	#
	# home_page = frappe.db.sql("""select name from `tabWebsite Route`
	# 	where (name=%s or docname=%s) and name!='index'""", (original_home_page, original_home_page))
	# home_page = home_page[0][0] if home_page else original_home_page
	#
	# frappe.db.set_value("Website Settings", "Website Settings", "home_page", home_page)
