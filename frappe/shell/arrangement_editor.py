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
from .navigation import SITE_LAYER, _boot_key, _sidebar_addresses, _sidebar_layers, resolve_navigation
from .navigation_filter import NavigationContext


def read_arrangements(app: str, scope: str) -> dict:
	"""The rail, every sidebar, the layouts and the version of one app at one level."""
	from .arrangement import get_navigation_layouts

	# First: a write that lands while the rows resolve must make this version stale, not the rows.
	version = level_version(app, scope)
	rail = _target("Rail", app, scope)
	context = NavigationContext(app)
	offered = {
		key: address
		for address in _sidebar_addresses(app)
		# The site level arranges what everyone gets, not what this manager's blocked modules leave them.
		if (scope == "site" or context.address_is_offered(*address))
		and not (scope == "site" and address[1].startswith("user:"))
		and (key := _boot_key(address))
	}
	layers = _sidebar_layers(list(offered.values()))

	rail_rows = _editor_rows(rail, scope)
	sidebars = {
		key: _editor_rows(_target("Sidebar", key, scope), scope, layers.get(address, {}))
		for key, address in offered.items()
	}
	_mark([rail_rows, *sidebars.values()], scope)

	return {
		"version": version,
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

	stored = _own_sidebars(rail, scope)
	_check_rows(rail, scope, reduced, stored)

	doomed = _unopened(rail, scope, reduced, stored)
	reduced = [(target, rows) for target, rows in reduced if target.layer.get("key") not in doomed]
	_check_caps(
		rail,
		[row for _target_, rows in reduced for row in _added(rows)],
		[target for target, _rows in reduced],
		ignoring={name for key, name in stored.items() if key in doomed},
	)

	for target, rows in reduced:
		_write(target, rows)

	for key in doomed & stored.keys():
		frappe.delete_doc("Sidebar", stored[key], ignore_permissions=True, delete_permanently=True)

	return resolve_navigation(app)


def level_version(app: str, scope: str, for_update: bool = False) -> str:
	"""A hash of this level's records of the app, which changes with any write to them."""
	user = frappe.session.user if scope == "user" else SITE_LAYER
	records = []

	for doctype in CONTAINERS:
		table = frappe.qb.DocType(doctype)
		query = frappe.qb.from_(table).select(table.name, table.modified)
		query = query.where((table.app == app) & (table.standard == 0) & (table.user == user))

		if doctype == "Sidebar":
			query = query.where(table.key.notnull() | table.link_doctype.notnull())

		# A locking read: the save compares against what a save that committed since wrote.
		query = query.for_update() if for_update else query
		records += [(doctype, name, str(modified)) for name, modified in query.run()]

	return hashlib.sha1(json.dumps(sorted(records)).encode()).hexdigest()


def _editor_rows(target: Target, scope: str, layers: dict | None = None) -> list[dict]:
	"""One container up to this level, hidden rows kept, with what the editor draws a row by."""
	extra = {"layers": layers} if layers is not None else {}
	rows = target.resolve(upto=scope, keep_hidden=True, **extra)

	if scope == "user":
		rows = _with_no_access(
			rows, target.resolve(upto=scope, keep_hidden=True, check_permission=False, **extra)
		)

	return _with_hidden_by(target, rows, scope, extra)


def _with_hidden_by(target: Target, rows: list[dict], scope: str, extra: dict) -> list[dict]:
	"""Each hidden row, with the level whose layer hid it."""
	if not any(row.get("hidden") for row in rows):
		return rows

	by_site = set()

	if scope == "user":
		below = target.resolve(upto="site", keep_hidden=True, check_permission=False, **extra)
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
		frappe.throw(
			_("Someone changed this since you opened it. Reload to see their changes."),
			frappe.TimestampMismatchError,
		)


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


def _check_rows(rail: Target, scope: str, reduced: list[tuple[Target, list[dict]]], stored: dict[str, str]):
	"""Steps 3 to 5: each own row's checks, then which rows may open which sidebar."""
	for target, rows in reduced:
		_validate_own_rows(target, target.layer["doctype"], scope, _added(rows))

	kept = {key for key in stored if key not in _by_key(reduced, scope)} | {
		key for key, rows in _by_key(reduced, scope).items() if rows
	}
	seen = set()

	for target, rows in reduced:
		for row in (row for row in rows if row.get("opens_sidebar")):
			_check_opener(row, target.layer["doctype"], scope, kept, seen)

	if not any(target.layer["doctype"] == "Rail" for target, _rows in reduced):
		emptied = set(_by_key(reduced, scope)) - kept
		opened = _stored_openers(rail) & emptied

		if opened:
			frappe.throw(
				_("{0}: Remove the item that opens it first.").format(frappe.bold(", ".join(sorted(opened)))),
				title=_("Not an Arrangement"),
			)


def _check_opener(row: dict, container: str, scope: str, kept: set[str], seen: set[str]):
	sidebar = row["opens_sidebar"]

	if not isinstance(sidebar, str):
		frappe.throw(_("A sidebar is named by its key."), title=_("Not an Arrangement"))

	if container != "Rail":
		frappe.throw(_("Only a rail item can open a sidebar."), title=_("Not an Arrangement"))

	if not (sidebar.startswith(f"{scope}:") and sidebar in kept):
		frappe.throw(
			_("{0} is not a sidebar this level added.").format(frappe.bold(sidebar)),
			title=_("Not an Arrangement"),
		)

	if sidebar in seen:
		frappe.throw(_("This sidebar already opens from another item."), title=_("Not an Arrangement"))

	seen.add(sidebar)


def _by_key(reduced: list[tuple[Target, list[dict]]], scope: str) -> dict[str, list[dict]]:
	"""The sidebars this level added that the payload names, by key."""
	# Not a person's arrangement of the site's sidebar: that sidebar is the site's, whatever the person does to it.
	return {
		target.layer["key"]: rows
		for target, rows in reduced
		if target.layer["doctype"] == "Sidebar" and target.layer.get("key", "").startswith(f"{scope}:")
	}


def _own_sidebars(rail: Target, scope: str) -> dict[str, str]:
	"""The own sidebars this level has stored for the app, by key."""
	filters = {"app": rail.app, "standard": 0, "user": rail.layer["user"], "key": ("like", f"{scope}:%")}

	return dict(frappe.get_all("Sidebar", filters=filters, fields=["key", "name"], as_list=True))


def _stored_openers(rail: Target) -> set[str]:
	"""The sidebars the stored rail's rows open."""
	record = _existing(rail)

	if not record:
		return set()

	filters = {"parent": record, "parenttype": "Rail", "opens_sidebar": ("is", "set")}

	return set(frappe.get_all("Navigation Item", filters=filters, pluck="opens_sidebar"))


def _unopened(
	rail: Target, scope: str, reduced: list[tuple[Target, list[dict]]], stored: dict[str, str]
) -> set[str]:
	"""Step 8: the keys of this level's own sidebars, stored or sent, that no rail row of this level opens after the save."""
	rails = [rows for target, rows in reduced if target.layer["doctype"] == "Rail"]
	opened = (
		{row["opens_sidebar"] for row in rails[0] if row.get("opens_sidebar")}
		if rails
		else _stored_openers(rail)
	)

	return (set(stored) | set(_by_key(reduced, scope))) - opened
