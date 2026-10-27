# The command palette's places: the doctypes a person can go to or create, and the apps they can open.

import frappe
from frappe import _

from .boot import app_screen, index_tiles
from .doctypes import get_shell_doctypes
from .links import canonical_path
from .permissions import has_app_permission, may_enter_any_prefix


@frappe.whitelist(methods=["GET"])
def places() -> dict:
	"""The readable doctypes with their app, address and create right; the apps; each app's title."""
	if not may_enter_any_prefix():
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	doctypes = place_doctypes()
	apps = [{"app": tile["app"], "title": tile["title"], "route": tile["route"]} for tile in index_tiles()]
	owners = {doctype["app"] for doctype in doctypes}
	return {
		"doctypes": doctypes,
		"apps": apps,
		"titles": {app: app_screen(app)["title"] for app in sorted(owners)},
	}


def place_doctypes() -> list[dict]:
	"""Each doctype the user can read that has an address in an app they may enter, by name."""
	# `can_read` and `can_create` are desk v1's own lists: no "User Cannot Search", no single to create.
	user = frappe.get_user()
	readable = user.get_can_read()
	creatable = set(user.can_create)
	doctypes = get_shell_doctypes()
	table, owners = doctypes["table"], doctypes["owners"]
	singles = set(table["singles"])
	enterable = {app: has_app_permission(app) for app in set(owners.values())}

	return [
		{
			"name": doctype,
			"app": owners.get(doctype, "frappe"),
			"route": canonical_path(doctype, doctype if doctype in singles else None),
			"can_create": doctype in creatable,
		}
		for doctype in sorted(readable)
		if doctype in table["doctypes"] and enterable.get(owners.get(doctype, "frappe"))
	]
