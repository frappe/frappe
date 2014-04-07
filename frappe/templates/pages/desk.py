# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

no_sitemap = 1
no_cache = 1
base_template_path = "templates/pages/desk.html"

import frappe, os

def get_context(context):
	hooks = frappe.get_hooks()
	return {
		"build_version": str(os.path.getmtime(os.path.join(frappe.local.sites_path, "assets", "js",
			"frappe.min.js"))),
		"include_js": hooks["app_include_js"],
		"include_css": hooks["app_include_css"]
	}
