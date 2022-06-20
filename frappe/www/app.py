# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
no_cache = 1

import os
import re

import frappe
import frappe.sessions
from frappe import _
from frappe.utils.jinja_globals import bundled_asset, is_rtl


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.throw(_("Log in to access this page."), frappe.PermissionError)
	elif frappe.db.get_value("User", frappe.session.user, "user_type") == "Website User":
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	hooks = frappe.get_hooks()
	# this needs commit
	csrf_token = frappe.sessions.get_csrf_token()

	frappe.db.commit()

	context.update(
		{
			"no_cache": 1,
			"build_version": frappe.utils.get_build_version(),
			"include_css": hooks["app_include_css"],
			"layout_direction": "rtl" if is_rtl() else "ltr",
			"lang": frappe.local.lang,
			"sounds": hooks["sounds"],
			"csrf_token": csrf_token,
			"desk_theme": frappe.get_cached_value("User", frappe.session.user, "desk_theme") or "Light",
			"google_analytics_id": frappe.conf.get("google_analytics_id"),
			"google_analytics_anonymize_ip": frappe.conf.get("google_analytics_anonymize_ip"),
			"mixpanel_id": frappe.conf.get("mixpanel_id"),
		}
	)

	return context


@frappe.whitelist()
def get_boot_info():
	boot = frappe.sessions.get()
	boot.script_files = [bundled_asset(path) for path in frappe.get_hooks("app_include_js")]

	return boot
