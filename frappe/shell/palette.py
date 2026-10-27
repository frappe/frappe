# The command palette's places: the doctypes a person can go to or create, and the apps they can open.

from zoneinfo import ZoneInfo

import frappe
from frappe import _
from frappe.utils import get_datetime, get_system_timezone

from .boot import app_screen, index_tiles, titled_visits
from .doctypes import get_shell_doctypes
from .links import canonical_path
from .permissions import has_app_permission, may_enter_any_prefix
from .route_history import Visit

RECENT_VISITS_LIMIT = 20


@frappe.whitelist(methods=["GET"])
def places() -> dict:
	"""The readable doctypes with their app, address and create right; the apps; each app's title; the recent visits."""
	if not may_enter_any_prefix():
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	doctypes = place_doctypes()
	apps = [{"app": tile["app"], "title": tile["title"], "route": tile["route"]} for tile in index_tiles()]
	owners = {doctype["app"] for doctype in doctypes}
	return {
		"doctypes": doctypes,
		"apps": apps,
		"titles": {app: app_screen(app)["title"] for app in sorted(owners)},
		"recent": recent_places(),
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


def recent_places() -> list[dict]:
	"""The person's last distinct list and record visits they can still open, titled, newest first."""
	zone = ZoneInfo(get_system_timezone())
	return [recent_place(visit, *heading, zone) for visit, *heading in titled_visits(RECENT_VISITS_LIMIT)]


def recent_place(visit: Visit, title: str, subtitle: str | None, zone: ZoneInfo) -> dict:
	"""A record says its doctype, a list or a single its app; `visited` in ms since the epoch, as the browser counts."""
	record = visit.name is not None
	return {
		"route": visit.route,
		"doctype": visit.doctype,
		"name": visit.name,
		"title": title,
		"kind": "record" if record else "list",
		"description": subtitle if record and subtitle else app_screen(visit.app)["title"],
		"visited": int(get_datetime(visit.visited).replace(tzinfo=zone).timestamp() * 1000),
	}
