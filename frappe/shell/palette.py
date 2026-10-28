# The command palette's places (the doctypes a person can go to or create, and the apps they can open)
# and its records.

from collections.abc import Iterable
from zoneinfo import ZoneInfo

import frappe
from frappe import _
from frappe.desk.doctype.global_search_settings.global_search_settings import (
	get_doctypes_for_global_search,
)
from frappe.desk.record_title import RecordTitles
from frappe.desk.search import search_widget
from frappe.utils import get_datetime, get_system_timezone

from .boot import index_tiles, titled_visits
from .doctypes import get_shell_doctypes
from .links import canonical_path
from .permissions import has_app_permission, may_enter_any_prefix
from .route_history import Visit
from .titles import app_screen

RECENT_VISITS_LIMIT = 20
RECORDS_PER_DOCTYPE = 3
RECORDS_IN_ALL = 10
SHORTEST_QUERY = 2


@frappe.desk_v2_only
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


@frappe.desk_v2_only
@frappe.whitelist(methods=["GET"])
def search_records(txt: str, doctype: str | None = None) -> list[dict]:
	"""Up to 10 records matching `txt`, 3 per doctype Go to lists, any named exactly `txt` first."""
	txt = txt.strip()
	if len(txt) < SHORTEST_QUERY:
		return []

	found = [row for each in searchable_doctypes(doctype) for row in records_of(each, txt)]
	return exact_first(found, txt)[:RECORDS_IN_ALL]


@frappe.desk_v2_only
@frappe.whitelist(methods=["GET"])
def search_doctype_records(doctype: str, txt: str) -> list[dict]:
	"""Up to 10 records of one doctype Go to lists, matching `txt`, any named exactly `txt` first."""
	txt = txt.strip()
	if len(txt) < SHORTEST_QUERY or not is_searchable(doctype):
		return []

	return exact_first(records_of(doctype, txt, RECORDS_IN_ALL), txt)


def place_doctypes() -> list[dict]:
	"""Each doctype the user can read that has an address in an app they may enter, by name."""
	# `can_read` and `can_create` are desk v1's own lists: no "User Cannot Search", no single to create.
	user = frappe.get_user()
	goes_to = enterable_owners(sorted(user.get_can_read()))
	creatable = set(user.can_create)
	singles = set(get_shell_doctypes()["table"]["singles"])

	return [
		{
			"name": doctype,
			"app": app,
			"route": canonical_path(doctype, doctype if doctype in singles else None),
			"can_create": doctype in creatable,
		}
		for doctype, app in goes_to.items()
	]


def enterable_owners(doctypes: Iterable[str]) -> dict[str, str]:
	"""Each of `doctypes` with an address in an app the person may enter, by its owner app, in order."""
	shell = get_shell_doctypes()
	addressed, owners = shell["table"]["doctypes"], shell["owners"]
	owned = {doctype: owners.get(doctype, "frappe") for doctype in doctypes if doctype in addressed}
	entered = {app for app in set(owned.values()) if has_app_permission(app)}
	return {doctype: app for doctype, app in owned.items() if app in entered}


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


def exact_first(found: list[dict], txt: str) -> list[dict]:
	# stable, so the rest keep their doctype order
	return sorted(found, key=lambda row: not is_exact(row["name"], txt))


def searchable_doctypes(current: str | None) -> list[str]:
	"""The current page's doctype, then the Global Search doctypes in their order, each one Go to lists."""
	readable = set(frappe.get_user().get_can_read())
	listed = get_doctypes_for_global_search()
	wanted = dict.fromkeys([current, *listed] if current else listed)
	return [
		doctype
		for doctype in enterable_owners(doctype for doctype in wanted if doctype in readable)
		if has_rows(doctype)
	]


def is_searchable(doctype: str) -> bool:
	return (
		doctype in frappe.get_user().get_can_read()
		and bool(enterable_owners([doctype]))
		and has_rows(doctype)
	)


def has_rows(doctype: str) -> bool:
	meta = frappe.get_meta(doctype)
	return not (meta.issingle or meta.istable or meta.is_virtual)


def records_of(doctype: str, txt: str, limit: int = RECORDS_PER_DOCTYPE) -> list[dict]:
	"""Titled by the title field, whatever Link fields show, with the address in its own app's prefix."""
	results = found_rows(doctype, txt, page_length=limit)
	if len(results) == limit and not any(is_exact(row.name, txt) for row in results):
		# a prefix match ties with the exact name, so a full page may have left it out
		named = found_rows(doctype, txt, filters={"name": ["like", escape_like(txt)]}, page_length=1)
		results = [*(row for row in named if is_exact(row.name, txt)), *results][:limit]
	titles = RecordTitles(doctype).of(results)
	return [
		{
			"doctype": doctype,
			"name": row.name,
			"label": titles[row.name],
			"route": canonical_path(doctype, row.name),
		}
		for row in results
	]


def found_rows(doctype: str, txt: str, **kwargs) -> list[frappe._dict]:
	# a hooked standard query (User's) may ignore as_dict and return tuples, name first
	return [
		row if isinstance(row, dict) else frappe._dict(name=row[0])
		for row in search_widget(doctype, txt, as_dict=True, **kwargs)
	]


def escape_like(txt: str) -> str:
	return txt.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def is_exact(name, txt: str) -> bool:
	return str(name).casefold() == txt.casefold()
