# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

no_sitemap = 1
no_cache = 1
base_template_path = "templates/pages/desk.html"

import os, json, re
import frappe
from frappe import _
import frappe.sessions

def get_context(context):
	if (frappe.session.user == "Guest" or
		frappe.db.get_value("User", frappe.session.user, "user_type")=="Website User"):

		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	hooks = frappe.get_hooks()
	boot = frappe.sessions.get()
	boot_json = json.dumps(boot)

	# remove script tags from boot
	boot_json = re.sub("\<script\>[^<]*\</script\>", "", boot_json)

	return {
		"build_version": str(os.path.getmtime(os.path.join(frappe.local.sites_path, "assets", "js",
			"desk.min.js"))),
		"include_js": hooks["app_include_js"],
		"include_css": hooks["app_include_css"],
		"boot": boot_json,
		"background_image": boot.user.background_image or boot.default_background_image,
		"google_analytics_id": frappe.conf.get("google_analytics_id")
	}
