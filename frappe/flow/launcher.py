# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Adds Flow's launcher to the pages of Desk and the apps-screen apps, which share no script."""

import frappe
from frappe import _
from frappe.utils import escape_html
from frappe.utils.jinja_globals import bundled_asset

HIDDEN_KEY = "hide_flow_launcher"  # a user default, set while the user hides the icon
DESK_V2_ROOT = "apps"  # frappe.shell's SHELL_ROOT, which the framework server may not import


def add_to_page(response, request):
	"""Adds the launcher's script to app pages of users who may use Flow and haven't hidden it."""
	if (
		request.method != "GET"
		or response.status_code != 200
		or response.mimetype != "text/html"
		or request.path.split("/")[1] not in get_app_roots()
		or not frappe.has_permission("Flow Session", "read")
		or is_hidden()
	):
		return

	head, body_end, tail = response.get_data(as_text=True).rpartition("</body>")
	if body_end:
		src = bundled_asset("flow_launcher.bundle.js")
		labels = escape_html(frappe.as_json(get_labels(), indent=None))
		ready = " data-ready" if is_ready() else ""
		script = f'<script src="{src}" data-labels="{labels}"{ready} defer></script>'
		response.set_data(head + script + body_end + tail)


@frappe.whitelist(methods=["POST"])
def set_hidden(hidden: bool) -> None:
	"""Hides the icon from the user's app pages, or shows it again."""
	if hidden:
		frappe.defaults.set_user_default(HIDDEN_KEY, 1)
	else:
		frappe.defaults.clear_user_default(HIDDEN_KEY)


def get_app_roots() -> set[str]:
	"""The first path segment of each apps screen route; Frappe's own is the Desk. Desk v2's
	pages are under its own root."""
	routes = (app.get("route") or "" for app in frappe.get_hooks("add_to_apps_screen"))
	return ({route.strip("/").split("/")[0] for route in routes} - {""}) | {DESK_V2_ROOT}


def is_ready() -> bool:
	"""Whether the user sees an enabled model and agent, so a chat can start (the palette's
	"Ask Flow" waits for it)."""
	return all(
		frappe.has_permission(doctype, "read")
		and frappe.get_list(doctype, filters={"enabled": 1}, pluck="name", limit=1)
		for doctype in ("Flow Model", "Flow Agent")
	)


def is_hidden() -> bool:
	"""Whether the user hid the icon."""
	return bool(frappe.defaults.get_user_default(HIDDEN_KEY))


def get_labels() -> dict[str, str]:
	"""The launcher's words in the user's language, which the apps' pages can't translate."""
	return {
		"open": _("Open Flow"),
		"hide": _("Hide Flow icon"),
		"hidden": _("Flow icon hidden"),
		"turn_on": _("Turn it back on in {0}"),
		"settings": _("Settings"),
		"undo": _("Undo"),
		"close": _("Close"),
		"minimize": _("Minimize"),
		"float": _("Float"),
		"left": _("Dock to the left"),
		"right": _("Dock to the right"),
		"full": _("Full screen"),
		"exit_full": _("Exit full screen"),
	}
