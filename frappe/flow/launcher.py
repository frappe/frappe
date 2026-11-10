# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Adds Flow's launcher to the pages of Desk, Studio and the apps-screen apps, which share no script."""

import frappe
from frappe.utils import get_assets_json
from frappe.utils.jinja_globals import bundled_asset

ISLAND = "frappe.flow.chat"
# apps with an integration of their own, where neither the panel nor Cmd/Ctrl+I belongs
WITHOUT_LAUNCHER = {"raven"}
# Frappe's own pages that aren't on the apps screen; "apps" is desk v2's frappe.shell SHELL_ROOT,
# which the framework server may not import
OWN_ROOTS = {"studio", "apps"}


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
		assets = get_assets_json()
		ready = " data-ready" if is_ready() else ""
		script = (
			f'<script src="{bundled_asset("flow_launcher.bundle.js")}" defer{ready}'
			f' data-island="{assets.get(f"{ISLAND}.island.js", "")}"'
			f' data-island-css="{assets.get(f"{ISLAND}.island.css", "")}"></script>'
		)
		response.set_data(head + script + body_end + tail)


def get_app_roots() -> set[str]:
	"""The first path segment of each apps screen route, of Studio and of desk v2; Frappe's own
	is the Desk."""
	routes = (app.get("route") or "" for app in frappe.get_hooks("add_to_apps_screen"))
	return ({route.strip("/").split("/")[0] for route in routes} | OWN_ROOTS) - {""} - WITHOUT_LAUNCHER


def is_ready() -> bool:
	"""Whether the user sees an enabled model and agent, so a chat can start (the palette's
	"Ask Flow" waits for it)."""
	return all(
		frappe.has_permission(doctype, "read")
		and frappe.get_list(doctype, filters={"enabled": 1}, pluck="name", limit=1)
		for doctype in ("Flow Model", "Flow Agent")
	)
