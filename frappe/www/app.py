# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
no_cache = 1

import json
import os
import re

import frappe
import frappe.sessions
from frappe import _
from frappe.utils.jinja_globals import is_rtl

SCRIPT_TAG_PATTERN = re.compile(r"\<script[^<]*\</script\>")
CLOSING_SCRIPT_TAG_PATTERN = re.compile(r"</script\>")


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.throw(_("Log in to access this page."), frappe.PermissionError)
	elif (
		frappe.db.get_value("User", frappe.session.user, "user_type", order_by=None) == "Website User"
	):
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	hooks = frappe.get_hooks()
	try:
		boot = frappe.sessions.get()
	except Exception as e:
		raise frappe.SessionBootFailed from e

	# this needs commit
	csrf_token = frappe.sessions.get_csrf_token()

	frappe.db.commit()

	boot_json = frappe.as_json(boot, indent=None, separators=(",", ":"))

	# remove script tags from boot
	boot_json = SCRIPT_TAG_PATTERN.sub("", boot_json)

	# TODO: Find better fix
	boot_json = CLOSING_SCRIPT_TAG_PATTERN.sub("", boot_json)
	boot_json = json.dumps(boot_json)

	include_js = hooks.get("app_include_js", []) + frappe.conf.get("app_include_js", [])
	include_css = hooks.get("app_include_css", []) + frappe.conf.get("app_include_css", [])

	context.update(
		{
			"no_cache": 1,
			"build_version": frappe.utils.get_build_version(),
			"include_js": include_js,
			"include_css": include_css,
			"layout_direction": "rtl" if is_rtl() else "ltr",
			"lang": frappe.local.lang,
			"sounds": hooks["sounds"],
			"boot": boot if context.get("for_mobile") else boot_json,
			"desk_theme": boot.get("desk_theme") or "Light",
			"csrf_token": csrf_token,
			"google_analytics_id": frappe.conf.get("google_analytics_id"),
			"google_analytics_anonymize_ip": frappe.conf.get("google_analytics_anonymize_ip"),
			"mixpanel_id": frappe.conf.get("mixpanel_id"),
		}
	)

	return context


@frappe.whitelist()
def get_desk_assets(build_version):
	"""Get desk assets to be loaded for mobile app"""
	data = get_context({"for_mobile": True})
	assets = [{"type": "js", "data": ""}, {"type": "css", "data": ""}]

	if build_version != data["build_version"]:
		# new build, send assets
		for path in data["include_js"]:
			# assets path shouldn't start with /
			# as it points to different location altogether
			if path.startswith("/assets/"):
				path = path.replace("/assets/", "assets/")
			try:
				with open(os.path.join(frappe.local.sites_path, path)) as f:
					assets[0]["data"] = assets[0]["data"] + "\n" + frappe.safe_decode(f.read(), "utf-8")
			except OSError:
				pass

		for path in data["include_css"]:
			if path.startswith("/assets/"):
				path = path.replace("/assets/", "assets/")
			try:
				with open(os.path.join(frappe.local.sites_path, path)) as f:
					assets[1]["data"] = assets[1]["data"] + "\n" + frappe.safe_decode(f.read(), "utf-8")
			except OSError:
				pass

	return {"build_version": data["build_version"], "boot": data["boot"], "assets": assets}
