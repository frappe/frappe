# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import os

no_cache = 1

import json
import re
from urllib.parse import urlencode

import nts
import nts.sessions
from nts import _
from nts.utils.jinja_globals import is_rtl

SCRIPT_TAG_PATTERN = re.compile(r"\<script[^<]*\</script\>")
CLOSING_SCRIPT_TAG_PATTERN = re.compile(r"</script\>")


def get_context(context):
	if nts.session.user == "Guest":
		nts.response["status_code"] = 403
		nts.msgprint(_("Log in to access this page."))
		nts.redirect(f"/login?{urlencode({'redirect-to': nts.request.path})}")
	elif nts.db.get_value("User", nts.session.user, "user_type", order_by=None) == "Website User":
		nts.throw(_("You are not permitted to access this page."), nts.PermissionError)

	hooks = nts.get_hooks()
	try:
		boot = nts.sessions.get()
	except Exception as e:
		raise nts.SessionBootFailed from e

	# this needs commit
	csrf_token = nts.sessions.get_csrf_token()

	nts.db.commit()

	boot_json = nts.as_json(boot, indent=None, separators=(",", ":"))

	# remove script tags from boot
	boot_json = SCRIPT_TAG_PATTERN.sub("", boot_json)

	# TODO: Find better fix
	boot_json = CLOSING_SCRIPT_TAG_PATTERN.sub("", boot_json)

	include_js = hooks.get("app_include_js", []) + nts.conf.get("app_include_js", [])
	include_css = hooks.get("app_include_css", []) + nts.conf.get("app_include_css", [])
	include_icons = hooks.get("app_include_icons", [])
	nts.local.preload_assets["icons"].extend(include_icons)

	if nts.get_system_settings("enable_telemetry") and os.getenv("nts_SENTRY_DSN"):
		include_js.append("sentry.bundle.js")

	context.update(
		{
			"no_cache": 1,
			"build_version": nts.utils.get_build_version(),
			"include_js": include_js,
			"include_css": include_css,
			"include_icons": include_icons,
			"layout_direction": "rtl" if is_rtl() else "ltr",
			"lang": nts.local.lang,
			"sounds": hooks["sounds"],
			"boot": boot if context.get("for_mobile") else json.loads(boot_json),
			"desk_theme": boot.get("desk_theme") or "Light",
			"csrf_token": csrf_token,
			"google_analytics_id": nts.conf.get("google_analytics_id"),
			"google_analytics_anonymize_ip": nts.conf.get("google_analytics_anonymize_ip"),
			"app_name": (
				nts.get_website_settings("app_name") or nts.get_system_settings("app_name") or "nts"
			),
		}
	)

	return context
