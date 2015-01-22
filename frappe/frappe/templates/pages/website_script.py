# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import frappe

no_sitemap = 1
base_template_path = "templates/pages/website_script.js"

def get_context(context):
	script_context = { "javascript": frappe.db.get_value('Website Script', None, 'javascript') }
	
	if not frappe.conf.developer_mode:
		script_context["google_analytics_id"] = frappe.db.get_value("Website Settings", "Website Settings",
			"google_analytics_id")
	
	return script_context
