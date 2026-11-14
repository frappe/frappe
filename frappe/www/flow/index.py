# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""The /flow page: Flow's chat island, full page, with the signed-in user's boot data rendered
into it."""

from urllib.parse import urlencode

import frappe

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		# back to the page asked for, such as a chat someone shared
		frappe.local.flags.redirect_location = f"/login?{urlencode({'redirect-to': frappe.request.path})}"
		raise frappe.Redirect
	from frappe.flow.launcher import ISLAND
	from frappe.utils import get_assets_json

	assets = get_assets_json()
	context.island_js = assets.get(f"{ISLAND}.island.js")
	context.island_css = assets.get(f"{ISLAND}.island.css")
	context.boot = get_boot()
	return context


def get_boot() -> dict:
	from frappe.flow.api import boot

	csrf_token = frappe.sessions.get_csrf_token()
	flow_boot = boot()
	# the token is written to the session on first use, as /app does, and a site's Grove key
	# adds its provider on first open
	frappe.db.commit()  # nosemgrep: frappe-manual-commit
	return {
		"csrf_token": csrf_token,
		"site_name": frappe.local.site,
		"socketio_port": frappe.conf.socketio_port,
		"flow_boot": flow_boot,
	}
