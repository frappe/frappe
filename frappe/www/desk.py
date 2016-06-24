# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

no_sitemap = 1
no_cache = 1
base_template_path = "templates/pages/desk.html"

import os, re
import frappe
from frappe import _
import frappe.sessions

def get_context(context):
	if (frappe.session.user == "Guest" or
		frappe.db.get_value("User", frappe.session.user, "user_type")=="Website User"):
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	hooks = frappe.get_hooks()
	boot = frappe.sessions.get()

	# this needs commit
	csrf_token = frappe.sessions.get_csrf_token()

	frappe.db.commit()

	boot_json = frappe.as_json(boot)

	# remove script tags from boot
	boot_json = re.sub("\<script\>[^<]*\</script\>", "", boot_json)

	return {
		"build_version": get_build_version(),
		"include_js": hooks["app_include_js"],
		"include_css": hooks["app_include_css"],
		"sounds": hooks["sounds"],
		"boot": boot if context.get("for_mobile") else boot_json,
		"csrf_token": csrf_token,
		"background_image": boot.user.background_image or boot.default_background_image,
		"google_analytics_id": frappe.conf.get("google_analytics_id")
	}

@frappe.whitelist()
def get_desk_assets(build_version):
	"""Get desk assets to be loaded for mobile app"""
	data = get_context({"for_mobile": True})
	assets = [{"type": "js", "data": ""}, {"type": "css", "data": ""}]

	if build_version != data["build_version"]:
		# new build, send assets
		for path in data["include_js"]:
			with open(os.path.join(frappe.local.sites_path, path) ,"r") as f:
				assets[0]["data"] = assets[0]["data"] + "\n" + unicode(f.read(), "utf-8")

		for path in data["include_css"]:
			with open(os.path.join(frappe.local.sites_path, path) ,"r") as f:
				assets[1]["data"] = assets[1]["data"] + "\n" + unicode(f.read(), "utf-8")

	return {
		"build_version": data["build_version"],
		"boot": data["boot"],
		"assets": assets
	}

def get_build_version():
	return str(os.path.getmtime(os.path.join(frappe.local.sites_path, "assets", "js",
			"desk.min.js")))
