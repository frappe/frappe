# ARRANGEMENT EDITOR — the one read and the one write behind the navigation editor.

# The editor holds a draft of every container of one app at one level, so it reads them all at
# once and writes the changed ones in one request: a refusal anywhere writes nothing.

import hashlib
import json

import frappe
from frappe import _

from .arrangement import (
	CONTAINERS,
	Target,
	_as_items,
	_check_caps,
	_existing,
	_is_site_administrator,
	_target,
	_validate_own_rows,
	_with_no_access,
	_write,
	lock_level,
	reduce_container,
)
from .navigation import SITE_LAYER, _boot_key, _sidebar_addresses, resolve_navigation
from .navigation_filter import NavigationContext

MISMATCH = "Someone changed this since you opened it. Reload to see their changes."


def read_arrangements(app: str, scope: str) -> dict:
	"""The rail, every sidebar, the layouts and the version of one app at one level."""
	# A sidebar the person's blocked modules remove is left out, not refused: it is not theirs to arrange.
	from .arrangement import get_navigation_layouts

	rail = _target("Rail", app, scope)
	context = NavigationContext(app)
	targets = {
		key: _target("Sidebar", key, scope)
		for address in _sidebar_addresses(app)
		if context.address_is_offered(*address)
		and not (scope == "site" and address[1].startswith("user:"))
		and (key := _boot_key(address))
	}
	rail_rows = _editor_rows(rail, scope)
	sidebars = {key: _editor_rows(target, scope) for key, target in targets.items()}
	_mark([rail_rows, *sidebars.values()], scope)

	return {
		"version": level_version(app, scope),
		"can_edit_site": _is_site_administrator(),
		"navigation_layouts": get_navigation_layouts(app),
		"rail": rail_rows,
		"sidebars": sidebars,
	}


def write_arrangements(app: str, scope: str, containers: str | dict, version: str) -> dict:
	"""Store each container the draft changed, in the order the editor's spec lists the checks."""
	payload = _payload(containers)
	rail, sidebars = _gate(app, scope, payload)

	lock_level(rail)
	_check_version(app, scope, version)

	reduced = []
	if payload["rail"] is not None:
		_refuse_rail_parents(payload["rail"])
		reduced.append((rail, reduce_container(rail, "Rail", scope, payload["rail"])))

	for key, target in sidebars.items():
		reduced.append((target, reduce_container(target, "Sidebar", scope, payload["sidebars"][key])))

	_check_rows(app, scope, reduced, payload)
	_check_caps(
		rail, [row for _target_, rows in reduced for row in _added(rows)], [t for t, _rows in reduced]
	)

	for target, rows in reduced:
		_write(target, rows)

	_delete_unreferenced_sidebars(rail, scope)

	return resolve_navigation(app)


def level_version(app: str, scope: str, for_update: bool = False) -> str:
	"""A hash of this level's records of the app, which changes with any write to them."""
	# One person's write to a container and another's to a different one still differ: the editor
	# holds all of them, so a stale draft of any is a stale draft.
	user = frappe.session.user if scope == "user" else SITE_LAYER
	records = []

	for doctype in CONTAINERS:
		table = frappe.qb.DocType(doctype)
		query = frappe.qb.from_(table).select(table.name, table.modified)
		query = query.where((table.app == app) & (table.standard == 0) & (table.user == user))

		# A desk v1 sidebar carries no address and is no container of the editor.
		if doctype == "Sidebar":
			query = query.where(table.key.notnull() | table.link_doctype.notnull())

		# A locking read: the save compares against what a save that committed since wrote.
		query = query.for_update() if for_update else query
		records += [(doctype, name, str(modified)) for name, modified in query.run()]

	return hashlib.sha1(json.dumps(sorted(records)).encode()).hexdigest()


# What the read adds to each row


def _editor_rows(target: Target, scope: str) -> list[dict]:
	"""One container up to this level, hidden rows kept, with what the editor draws a row by."""
	rows = target.resolve(upto=scope, keep_hidden=True)

	if scope == "user":
		rows = _with_no_access(rows, target.resolve(upto=scope, keep_hidden=True, check_permission=False))

	return _with_hidden_by(target, rows, scope)


def _with_hidden_by(target: Target, rows: list[dict], scope: str) -> list[dict]:
	"""Each hidden row, with the level whose layer hid it."""
	if not any(row.get("hidden") for row in rows):
		return rows

	# A person's own hide only counts for what the site left showing.
	by_site = set()

	if scope == "user":
		below = target.resolve(upto="site", keep_hidden=True, check_permission=False)
		by_site = {row["key"] for row in below if row.get("hidden")}

	return [
		{**row, "hidden_by": "site" if row["key"] in by_site or scope == "site" else "user"}
		if row.get("hidden")
		else row
		for row in rows
	]


def _mark(lists: list[list[dict]], scope: str):
	"""Merge what each type's `navigation_item_markers` entry says about its rows, e.g. `view_deleted`."""
	# One call per type over every container, so a marker costs one query however many sidebars there are.
	by_type: dict[str, list[dict]] = {}

	for row in (row for rows in lists for row in rows):
		by_type.setdefault(row.get("item_type"), []).append(row)

	for item_type, paths in frappe.get_hooks("navigation_item_markers", default={}).items():
		if item_type not in by_type:
			continue

		marks = {}
		for path in paths:
			marks |= frappe.get_attr(path)(by_type[item_type], scope)

		for row in by_type[item_type]:
			row |= marks.get(row["key"], {})


# The write, check by check


def _payload(containers: str | dict) -> dict:
	"""`{"rail": list | None, "sidebars": {key: list}}` from what the client sent."""
	if isinstance(containers, str):
		try:
			containers = json.loads(containers)
		except ValueError:
			containers = None

	sidebars = containers.get("sidebars", {}) if isinstance(containers, dict) else None

	if not isinstance(containers, dict) or not isinstance(sidebars, dict):
		frappe.throw(_("The containers are a rail and a map of sidebars."), title=_("Not an Arrangement"))

	if not all(isinstance(key, str) for key in sidebars):
		frappe.throw(_("A sidebar is named by its address or key."), title=_("Not an Arrangement"))

	return {"rail": containers.get("rail"), "sidebars": sidebars}


def _gate(app: str, scope: str, payload: dict) -> tuple[Target, dict[str, Target]]:
	"""Step 1: the endpoint's gate for the rail, which also gates the app, and for each sidebar named."""
	rail = _target("Rail", app, scope)
	sidebars = {key: _target("Sidebar", key, scope, new_in=app) for key in payload["sidebars"]}

	for key, target in sidebars.items():
		if target.app != app:
			frappe.throw(
				_("{0} is not a sidebar of {1}.").format(frappe.bold(key), app), title=_("Not an Arrangement")
			)

	return rail, sidebars


def _check_version(app: str, scope: str, version: str):
	"""Step 2: refuse a draft that a save at this level has outdated."""
	if level_version(app, scope, for_update=True) != version:
		frappe.throw(_(MISMATCH), frappe.TimestampMismatchError)


def _refuse_rail_parents(items: str | list):
	"""Step 4, the rail half: a rail row that holds rows. The depth cap would refuse it too, with another message."""
	rows = _as_items(items)
	parents = {row["parent_key"] for row in rows} & {row["key"] for row in rows}

	if parents:
		frappe.throw(
			_("{0}: Move its children out first.").format(frappe.bold(", ".join(sorted(parents)))),
			title=_("Not an Arrangement"),
		)


def _added(rows: list[dict]) -> list[dict]:
	return [row for row in rows if row.get("added")]


def _check_rows(app: str, scope: str, reduced: list[tuple[Target, list[dict]]], payload: dict):
	"""Steps 3 to 5: each own row's checks, then which rows may open which sidebar."""
	for target, rows in reduced:
		_validate_own_rows(target, target.layer["doctype"], scope, _added(rows))

	own_keys = _own_sidebar_keys(app, scope) | set(payload["sidebars"])
	seen = set()

	for target, rows in reduced:
		for row in (row for row in rows if row.get("opens_sidebar")):
			_check_opener(row, target.layer["doctype"], scope, own_keys, seen)


def _check_opener(row: dict, container: str, scope: str, own_keys: set[str], seen: set[str]):
	sidebar = row["opens_sidebar"]

	if container != "Rail":
		frappe.throw(_("Only a rail item can open a sidebar."), title=_("Not an Arrangement"))

	if not (sidebar.startswith(f"{scope}:") and sidebar in own_keys):
		frappe.throw(
			_("{0} is not a sidebar this level added.").format(frappe.bold(sidebar)),
			title=_("Not an Arrangement"),
		)

	if sidebar in seen:
		frappe.throw(_("This sidebar already opens from another item."), title=_("Not an Arrangement"))

	seen.add(sidebar)


def _own_sidebar_keys(app: str, scope: str) -> set[str]:
	"""The keys of the sidebars this level has stored for the app."""
	user = frappe.session.user if scope == "user" else SITE_LAYER
	filters = {"app": app, "standard": 0, "user": user, "key": ("like", f"{scope}:%")}

	return set(frappe.get_all("Sidebar", filters=filters, pluck="key"))


def _delete_unreferenced_sidebars(rail: Target, scope: str):
	"""Step 8: this level's own sidebars that no rail row of this level opens."""
	# How "Remove its sidebar" and deleting an own rail row reach the server.
	record = _existing(rail)
	opened = set()

	if record:
		opened = set(
			frappe.get_all(
				"Navigation Item",
				filters={"parent": record, "parenttype": "Rail", "opens_sidebar": ("is", "set")},
				pluck="opens_sidebar",
			)
		)

	user = rail.layer["user"]
	filters = {"app": rail.app, "standard": 0, "user": user, "key": ("like", f"{scope}:%")}

	for name, key in frappe.get_all("Sidebar", filters=filters, fields=["name", "key"], as_list=True):
		if key not in opened:
			frappe.delete_doc("Sidebar", name, ignore_permissions=True, delete_permanently=True)
