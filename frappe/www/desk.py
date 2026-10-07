# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import os

no_cache = 1

import json
import re
from urllib.parse import urlencode

import frappe
import frappe.sessions
from frappe import _
from frappe.utils.jinja_globals import is_rtl

SCRIPT_TAG_PATTERN = re.compile(r"\<script[^<]*\</script\>")
CLOSING_SCRIPT_TAG_PATTERN = re.compile(r"</script\>")


def get_session_boot_failed_error(e: Exception) -> "frappe.SessionBootFailed":
	"""Build the error shown when the desk fails to boot.

	The usual cause is a site whose database is behind the code, so say that plainly and give
	the command that fixes it instead of a bare traceback."""
	error = frappe.SessionBootFailed()

	if is_schema_out_of_date(e):
		error.title = _("This site needs a migration")
		error.message = _("Don't panic. Run this command and reload the page:")
		error.command = f"bench --site {frappe.local.site} migrate"

	return error


def is_schema_out_of_date(e: Exception) -> bool:
	"""True if this failure, or anything that caused it, was a missing table or column."""
	seen = set()

	while e is not None and id(e) not in seen:
		seen.add(id(e))

		if frappe.db.is_missing_table_or_column(e):
			return True

		e = e.__cause__ or e.__context__

	return False


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.response["status_code"] = 403
		frappe.msgprint(_("Log in to access this page."))
		frappe.redirect(f"/login?{urlencode({'redirect-to': frappe.request.path})}")

	elif frappe.session.data.user_type == "Website User":
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	try:
		boot = frappe.sessions.get()
	except Exception as e:
		raise get_session_boot_failed_error(e) from e

	# this needs commit
	csrf_token = frappe.sessions.get_csrf_token()

	hooks = frappe.get_hooks()
	app_include_js = hooks.get("app_include_js", []) + frappe.conf.get("app_include_js", [])
	app_include_css = hooks.get("app_include_css", []) + frappe.conf.get("app_include_css", [])
	app_include_icons = hooks.get("app_include_icons", [])

	if frappe.get_system_settings("enable_telemetry") and os.getenv("FRAPPE_SENTRY_DSN"):
		app_include_js.append("sentry.bundle.js")

	context.update(
		{
			"no_cache": 1,
			"build_version": frappe.utils.get_build_version(),
			"app_include_js": app_include_js,
			"app_include_css": app_include_css,
			"app_include_icons": app_include_icons,
			"layout_direction": "rtl" if is_rtl() else "ltr",
			"lang": frappe.local.lang,
			"sounds": hooks["sounds"],
			"boot": boot,
			"desk_theme": boot.get("desk_theme") or "Light",
			"csrf_token": csrf_token,
			"google_analytics_id": frappe.conf.get("google_analytics_id"),
			"google_analytics_anonymize_ip": frappe.conf.get("google_analytics_anonymize_ip"),
			"app_name": (
				frappe.get_website_settings("app_name") or frappe.get_system_settings("app_name") or "Frappe"
			),
		}
	)

	return context
