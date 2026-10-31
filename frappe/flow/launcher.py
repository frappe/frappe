# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Adds Flow's launcher to the pages of Desk and the apps-screen apps, which share no script."""

import frappe
from frappe.utils.jinja_globals import bundled_asset


def add_to_page(response, request):
	"""Adds the launcher's script to app pages of users who may use Flow."""
	if (
		request.method != "GET"
		or response.status_code != 200
		or response.mimetype != "text/html"
		or request.path.split("/")[1] not in get_app_roots()
		or not frappe.has_permission("Flow Session", "read")
	):
		return

	head, body_end, tail = response.get_data(as_text=True).rpartition("</body>")
	if body_end:
		script = f'<script src="{bundled_asset("flow_launcher.bundle.js")}" defer></script>'
		response.set_data(head + script + body_end + tail)


def get_app_roots() -> set[str]:
	"""The first path segment of each apps screen route; Frappe's own is the Desk."""
	routes = (app.get("route") or "" for app in frappe.get_hooks("add_to_apps_screen"))
	return {route.strip("/").split("/")[0] for route in routes} - {""}
