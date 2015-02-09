# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

no_sitemap = 1
no_cache = 1
base_template_path = "templates/pages/desk.html"

import os, json
import frappe
from frappe import _
import frappe.sessions
from frappe.utils.response import json_handler

def get_context(context):
	if (frappe.session.user == "Guest" or
		frappe.db.get_value("User", frappe.session.user, "user_type")=="Website User"):

		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	hooks = frappe.get_hooks()
	return {
		"build_version": str(os.path.getmtime(os.path.join(frappe.local.sites_path, "assets", "js",
			"frappe.min.js"))),
		"include_js": hooks["app_include_js"],
		"include_css": hooks["app_include_css"],
		"boot": json.dumps(frappe.sessions.get(), default=json_handler, indent=1, sort_keys=True)
	}
