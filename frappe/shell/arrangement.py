# ARRANGEMENT — the endpoints a person's navigation edits go through.

# A move is an anchor, not a position: a saved layer names the rows that moved and what each
# moved next to, so an item the app ships later still has somewhere to land.

# The client sends the whole ordered list it is showing and the server reduces it; a client
# that sent anchors would be diffing against a base it holds a stale copy of.

import json
import re
from collections.abc import Callable
from functools import partial
from typing import NamedTuple

import frappe
from frappe import _
from frappe.desk.doctype.navigation_item.navigation_item import OWN_KEY
from frappe.desk.doctype.navigation_item.nesting import SECTION, nesting_errors
from frappe.model.document import Document

from .navigation import (
	ITEM_FIELDS,
	NAVIGATION_LAYOUTS,
	SITE_LAYER,
	layout_below,
	rail_layouts,
	resolve_navigation,
	resolve_rail,
	resolve_sidebar,
)
from .navigation_filter import DERIVED_FROM_CHILDREN, NavigationContext, filter_items
from .permissions import has_app_permission

# `Sidebar` holds desk v1's `items` beside desk v2's `navigation_items`; naming the
# parentfield keeps a v2 write out of v1's sidebar.
CONTAINERS = ("Rail", "Sidebar")
ITEMS_FIELD = {"Rail": "items", "Sidebar": "navigation_items"}

# A scope, and the scope whose resolved list a save at that scope is relative to.
SCOPES = ("user", "site")
BELOW = {"user": "site", "site": "base"}

# Presentation only: an arrangement never changes what an item opens, but `opens_sidebar` is
# a link to a sidebar beside its target. `parent_key` is not here; reparenting travels as an anchor, whose `after`/`before` carry the parent.
OVERRIDABLE = ("label", "icon", "collapsible", "keep_closed", "opens_sidebar")

# What an own row stores: the whole item. `hidden` is absent because an own row is deleted, not
# hidden; `overrides` because it is no delta; `switches_app` because only a shipped row switches app.
OWN_FIELDS = tuple(field for field in ITEM_FIELDS if field not in ("hidden", "overrides", "switches_app"))

# A key a level adds is `OWN_KEY`; the editor makes it, so a new section's new children can name it
# before the first save. The prefixes are reserved against shipped keys.
RESERVED_PREFIXES = tuple(f"{scope}:" for scope in SCOPES)

# A Link's url: a path on this site, or an http(s) address. `\S`: a tab inside `/ /host` is stripped
# by the browser, which would turn the path into a protocol-relative address.
OWN_URL = re.compile(r"(?:/(?![/\\])|(?i:https?)://)\S*")

# What an own row opens, and so what `validate_own_row` judges.
OWN_TARGET = ("item_type", "link_doctype", "link_to", "url", "payload")

OWN_ROWS_PER_CONTAINER = 50
OWN_ROWS_PER_APP = 100


@frappe.desk_v2_only
@frappe.whitelist()
def get_arrangement(container: str, address: str, scope: str = "user") -> list[dict]:
	"""The list to arrange: resolved up to and including `scope`, hidden rows kept."""
	# Hidden rows stay, or hiding would be a one-way door.
	target = _target(container, address, scope)
	arrangement = target.resolve(upto=scope, keep_hidden=True)

	if scope == "site":
		return arrangement

	return _with_no_access(arrangement, target.resolve(upto=scope, keep_hidden=True, check_permission=False))


@frappe.desk_v2_only
@frappe.whitelist()
def save_arrangement(container: str, address: str, items: str | list, scope: str = "user") -> dict:
	"""Store one layer's arrangement and hand back the whole prefix's navigation."""
	target = _target(container, address, scope)
	lock_level(target)
	rows = reduce_container(target, container, scope, items)
	own_rows = [row for row in rows if row.get("added")]
	_check_caps(target, own_rows)
	_validate_own_rows(target, container, scope, own_rows)

	_write(target, rows)

	# The whole prefix comes back: hiding a rail item of type `Sidebar` changes which sidebars
	# are reachable, so a response scoped to the one list would be a half-truth.
	return resolve_navigation(target.app)


@frappe.desk_v2_only
@frappe.whitelist()
def get_arrangements(app: str, scope: str = "user") -> dict:
	"""Everything the navigation editor shows for one app at one level, in one call."""
	return _editor("read_arrangements")(app, scope)


@frappe.desk_v2_only
@frappe.whitelist()
def get_default_arrangements(app: str, scope: str = "user") -> dict:
	"""The rail and sidebars as the level below `scope` leaves them; the editor reads it when Reset to default is clicked."""
	return _editor("read_default_arrangements")(app, scope)


@frappe.desk_v2_only
@frappe.whitelist()
def save_arrangements(app: str, scope: str, containers: str | dict, version: str) -> dict:
	"""Store every container the editor changed in one transaction, and hand back the whole prefix's navigation."""
	return _editor("write_arrangements")(app, scope, containers, version)


def _editor(function: str) -> Callable:
	"""The editor's read or write, by name: the editor builds on this module, which must not import it back."""
	return frappe.get_attr(f"frappe.shell.arrangement_editor.{function}")


@frappe.desk_v2_only
@frappe.whitelist()
def reset_arrangement(container: str, address: str, scope: str = "user") -> dict:
	"""Delete one layer and hand back what the prefix resolves to without it."""
	target = _target(container, address, scope)
	lock_level(target)

	# A rail's reset takes its navigation layout with its rows; `_write` would keep the record.
	_delete(_locked(target))

	return resolve_navigation(target.app)


@frappe.desk_v2_only
@frappe.whitelist()
def save_navigation_layout(app: str, navigation_layout: str, scope: str = "user") -> dict:
	"""Set how this level draws the app's navigation, and hand back the whole prefix's navigation."""
	target = _target("Rail", app, scope)
	lock_level(target)

	if navigation_layout and navigation_layout not in NAVIGATION_LAYOUTS:
		frappe.throw(
			_("{0} is not a navigation layout.").format(frappe.bold(str(navigation_layout))),
			title=_("Not a Navigation Layout"),
		)

	# Stored as the value, a later change below would stop reaching this level.
	if navigation_layout == layout_below(rail_layouts(app), scope):
		navigation_layout = ""

	_write_layout(target, navigation_layout)

	return resolve_navigation(app)


@frappe.desk_v2_only
@frappe.whitelist()
def get_navigation_layouts(app: str) -> dict[str, str]:
	"""The layout each level sets for this app, blank where unset; the editor labels "Default (…)" with it."""
	if not isinstance(app, str) or app not in frappe.get_active_apps():
		frappe.throw(_("{0} is not an app on this site.").format(app), title=_("Not an App"))

	if not has_app_permission(app):
		frappe.throw(
			_("You are not permitted to arrange {0}.").format(app),
			frappe.PermissionError,
			title=_("Not Permitted"),
		)

	return {"standard": "", "site": "", "user": ""} | rail_layouts(app)


# What a level may add, and what it may see of what it added


def reduce_container(target: "Target", container: str, scope: str, items: str | list) -> list[dict]:
	"""The layer a client's whole list for one container reduces to; refuses a list nested too deeply."""
	below = target.resolve(upto=BELOW[scope], keep_hidden=True)
	desired = _as_items(items)

	_refuse_deep_nesting(container, below, desired, scope)
	rows = reduce_arrangement(_with_unseen_parents(target, below, desired, scope), desired, scope)

	# An empty reduction drops the layer, so this is the one place a save can become a reset.
	# It may only do so when the submission accounted for the whole list below.
	if below and not rows and not _accounts_for(below, desired):
		frappe.throw(
			_(
				"This arrangement does not cover everything {0} is showing, so it cannot be saved as one. Reload it, or reset it to go back to how it arrived."
			).format(frappe.bold(target.app)),
			title=_("Not an Arrangement"),
		)

	return rows


def _check_caps(
	target: "Target",
	own_rows: list[dict],
	saving: "list[Target] | None" = None,
	ignoring: "set[str] | None" = None,
):
	"""Refuse more own rows than one app may carry at this level; `_known` caps one container.

	`saving` is every layer this save writes, whose stored rows the payload replaces, and `ignoring`
	the records it deletes, whose rows are gone once it lands.
	"""
	if not own_rows:
		return

	lock_level(target)

	if len(own_rows) + _own_rows_elsewhere(target, saving or [target], ignoring or set()) > OWN_ROWS_PER_APP:
		frappe.throw(
			_("You can add up to {0} items to {1}, over its rail and all its sidebars.").format(
				OWN_ROWS_PER_APP, frappe.bold(target.app)
			),
			title=_("Too Many Items"),
		)


def lock_level(target: "Target"):
	"""Take this level's row first, so every save to one app's containers at this level runs in turn."""
	frappe.db.get_value("User", target.layer["user"] or "Administrator", "name", for_update=True)


def _own_rows_elsewhere(target: "Target", saving: "list[Target]", ignoring: "set[str]") -> int:
	"""The rows this level has added to this app outside the layers being saved or deleted, in one query."""
	item = frappe.qb.DocType("Navigation Item")
	saved = {_existing(layer) for layer in saving} | ignoring
	in_layers = None

	for container, layers in _layers_of(target).items():
		layers = [name for name in layers if name not in saved]

		if layers:
			criterion = (item.parenttype == container) & item.parent.isin(layers)
			in_layers = criterion if in_layers is None else in_layers | criterion

	if in_layers is None:
		return 0

	# `parentfield`: a `Sidebar` record's v1 `items` rows are not rows this level added.
	# A locking read: a plain one reads the transaction's snapshot, which a save that committed since misses.
	query = frappe.qb.from_(item).select(item.name).where((item.added == 1) & in_layers)
	query = query.where(item.parentfield.isin(list(ITEMS_FIELD.values())))

	return len(query.for_update().run())


def _layers_of(target: "Target") -> dict[str, list[str]]:
	"""This level's layers of this app, by container; a sidebar the app no longer ships has none that count."""
	# An own sidebar is no shipped address, and its rows count.
	filters = {"app": target.app, "standard": 0, "user": target.layer["user"]}
	rows = frappe.get_all("Sidebar", filters=filters, fields=["name", "key", "link_doctype", "link_to"])
	shipped = frappe.get_all(
		"Sidebar", filters={"app": target.app, "standard": 1}, fields=["link_doctype", "link_to"]
	)
	shipped = {(row.link_doctype, row.link_to) for row in shipped}

	return {
		"Rail": frappe.get_all("Rail", filters=filters, pluck="name"),
		"Sidebar": [row.name for row in rows if row.key or (row.link_doctype, row.link_to) in shipped],
	}


def _with_unseen_parents(target: "Target", below: list[dict], desired: list[dict], scope: str) -> list[dict]:
	"""The base, plus a section the filter dropped for being empty that an own row of the person's still sits in."""
	# `get_arrangement` lists such a section, so the save must know it, or the row would lose its parent.
	held = {item["key"] for item in below}
	parents = {item.get("parent_key") for item in desired if str(item.get("key")).startswith("user:")}

	if scope == "site" or not parents - held - {None}:
		return below

	unfiltered = target.resolve(upto=BELOW["user"], keep_hidden=True, check_permission=False)

	return [
		item
		for item in unfiltered
		if item["key"] in held or (item["key"] in parents and item.get("item_type") == SECTION)
	]


def _with_ancestors(keys: set[str], by_key: dict[str, dict]) -> set[str]:
	"""These keys and every section above them, so a row kept for the person keeps its parent."""
	# Only a section: any other inherited parent carries a destination the person may not read.
	found = set(keys)

	for key in keys:
		parent = by_key[key].get("parent_key")

		while parent in by_key and by_key[parent].get("item_type") == SECTION and parent not in found:
			found.add(parent)
			parent = by_key[parent].get("parent_key")

	return found


def _with_no_access(arrangement: list[dict], unfiltered: list[dict]) -> list[dict]:
	"""The person's list plus their own rows they can no longer open, so the editor can show and delete them."""
	# Inherited rows they cannot see stay out: those are not theirs to arrange. The unfiltered
	# list gives the order and the parents, so a section the filter dropped keeps its rows.
	visible = {item["key"]: item for item in arrangement}
	by_key = {item["key"]: item for item in unfiltered}
	kept = set(visible) | _with_ancestors({key for key in by_key if key.startswith("user:")}, by_key)
	listed = [item for item in unfiltered if item["key"] in kept]
	present = {item["key"] for item in listed}
	result = []

	for item in listed:
		row = {**visible.get(item["key"], {**item, "no_access": 1})}
		parent = item.get("parent_key")

		if parent in present:
			row["parent_key"] = parent
		else:
			row.pop("parent_key", None)

		result.append(row)

	return result


# Addressing and the gate


def _validate_own_rows(target: "Target", container: str, scope: str, own_rows: list[dict]):
	"""Validate the rows this save adds or changes; a row it keeps as stored may have lost its target since."""
	# Else one own row whose DocType was removed or whose access was taken away would block every save.
	stored = _stored_own_rows(target)
	changed = [row for row in own_rows if _identity(row) != stored.get(row["key"])]

	if not changed:
		return

	context = NavigationContext(target.app)

	for row in changed:
		validate_own_row(row, container, scope, context)


def _stored_own_rows(target: "Target") -> dict[str, tuple]:
	layer = _existing(target)

	if not layer:
		return {}

	rows = frappe.get_all(
		"Navigation Item",
		filters={"parent": layer, "parenttype": target.layer["doctype"], "added": 1},
		fields=["key", *OWN_TARGET],
	)

	return {row.key: _identity(row) for row in rows}


def _identity(row: dict) -> tuple:
	"""What an own row opens: the part a validator judges."""
	payload = row.get("payload")

	# A stored payload is text and a client may send it back as an object: compare what they mean.
	if isinstance(payload, str) and payload:
		try:
			payload = json.loads(payload)
		except ValueError:
			pass

	return (
		*(row.get(field) or "" for field in OWN_TARGET[:-1]),
		json.dumps(payload, sort_keys=True) if payload else "",
	)


def validate_own_row(row: dict, container: str, scope: str, context: NavigationContext):
	"""Refuse an own row of a kind that cannot be added, or whose target cannot be opened."""
	# The url and the payload are checked as the row is stored (`_check_own_content`).
	item_type = row.get("item_type")
	label = frappe.bold(row["key"])

	# Before the addable check, so a Sidebar row hears this and not "cannot be added".
	if container == "Sidebar" and (item_type == "Sidebar" or row.get("opens_sidebar")):
		frappe.throw(_("Remove its sidebar first."), title=_("Not an Arrangement"))

	if item_type not in context.addable_types:
		frappe.throw(
			_("{0} cannot be added: {1} is not a kind of item that a person or the site may add.").format(
				label, frappe.bold(str(item_type))
			),
			title=_("Not an Arrangement"),
		)

	if item_type == SECTION and container == "Rail":
		frappe.throw(
			_("A rail has no sections, so {0} cannot be added to it.").format(label),
			title=_("Not an Arrangement"),
		)

	if item_type == "Link" and not row.get("url"):
		frappe.throw(_("{0} needs a link to open.").format(label), title=_("Not an Arrangement"))

	_check_target(row, context)

	# One role-based pass over the context's cached sets, never a `has_permission` per row. A kind that
	# only reads its children holds no target to open, and Administrator opens everything.
	if (
		scope == "user"
		and context.rule(item_type) != DERIVED_FROM_CHILDREN
		and not filter_items([row], context)
	):
		frappe.throw(
			_("You cannot open the target of {0}, so you cannot add it to your own navigation.").format(
				label
			),
			title=_("No Access"),
		)

	for path in frappe.get_hooks("navigation_item_validators", default={}).get(item_type) or []:
		frappe.get_attr(f"{path}.validate_own_row")(row, container, scope, context)


def _check_target(row: dict, context: NavigationContext):
	"""The kind's own target doctype, if it names one, and a record that exists."""
	label = frappe.bold(row["key"])
	link_doctype = row.get("link_doctype")
	link_to = row.get("link_to")
	target = context.target(row["item_type"])

	if target and link_doctype != target:
		frappe.throw(
			_("{0} must open a {1}.").format(label, frappe.bold(target)), title=_("Not an Arrangement")
		)

	if row["item_type"] == "Record" and not (link_doctype and link_to):
		frappe.throw(
			_("{0} must name a document type and a document.").format(label), title=_("Not an Arrangement")
		)

	# Only a kind that opens a document: a Link or a Section names no target, and asking would tell
	# a person whether a document exists.
	if not (target or row["item_type"] == "Record"):
		return

	# A page an app draws in the frontend has no `Page` record, so a Page row only needs a name.
	if row["item_type"] == "Page" and link_to:
		return

	if not (
		link_to and frappe.db.exists("DocType", link_doctype) and frappe.db.exists(link_doctype, link_to)
	):
		frappe.throw(
			_("{0} points to {1} {2}, which does not exist.").format(
				label, link_doctype, frappe.bold(str(link_to))
			),
			title=_("Not an Arrangement"),
		)


class Target(NamedTuple):
	"""One addressed layer: whose app it is, how to resolve it, and where it is stored."""

	app: str
	resolve: Callable[..., list[dict]]
	layer: dict


def _target(container: str, address: str, scope: str, new_in: str = "") -> Target:
	"""Check the arguments and the caller, and describe the layer they name."""
	# `new_in`: the app a sidebar key with no record yet is created for; only the editor's save passes it.
	# No `user` argument anywhere here: the user scope is the session user and nothing else.

	# Explicit type checks: `validate_argument_types` only runs in a request, and `address` goes
	# straight into a `get_value` filter, where a list is a whole different query.
	if not all(isinstance(argument, str) for argument in (container, address, scope)):
		frappe.throw(_("A container, an address and a scope are each one name."))

	if container not in CONTAINERS:
		frappe.throw(_("{0} is not a navigation container.").format(container))

	if scope not in SCOPES:
		frappe.throw(_("{0} is not an arrangement scope.").format(scope))

	# `standard: 0`: an app's own layer and the site's arrangement of it share an address.
	stored = {"user": frappe.session.user if scope == "user" else SITE_LAYER, "standard": 0}

	# The site scope bypasses the permission filter: a list thinned to what the manager may see
	# would delete everyone else's items. Set once, so the read and the reduce base agree.
	check_permission = scope != "site"

	if container == "Rail":
		app = address
		resolve = partial(resolve_rail, app, check_permission=check_permission)
		stored |= {"app": app, "extends": ""}
	else:
		app, link_doctype, link_to = _sidebar_address(address, new_in, scope)
		resolve = partial(resolve_sidebar, link_doctype, link_to, check_permission=check_permission)
		# An own sidebar is stored by its key; a shipped one by its address.
		if link_doctype:
			stored |= {"app": app, "link_doctype": link_doctype, "link_to": link_to}
		elif scope == "site" and link_to.startswith("user:"):
			frappe.throw(_("{0} belongs to a person; the site cannot arrange it.").format(link_to))
		else:
			stored |= {"app": app, "key": link_to}

		# A sidebar this person's blocked module removes resolves to nothing, and a save against
		# nothing is a delete; refuse it instead.
		if check_permission and not NavigationContext("").address_is_offered(link_doctype, link_to):
			frappe.throw(
				_("{0} is not available to you, so there is nothing here to arrange.").format(
					frappe.bold(link_to)
				),
				title=_("Nothing to Arrange"),
			)

	# Before the gate: `has_app_permission` falls back to "not a Website User" for an app with
	# no hook, and an app not on the bench declares nothing.
	if app not in frappe.get_active_apps():
		frappe.throw(_("{0} is not an app on this site.").format(app))

	if not has_app_permission(app):
		frappe.throw(_("You are not permitted to arrange {0}.").format(app), frappe.PermissionError)

	if scope == "site" and not _is_site_administrator():
		frappe.throw(
			_("Only a System Manager may change what everyone on this site sees."),
			frappe.PermissionError,
		)

	return Target(app, resolve, {"doctype": container, **stored})


def _refuse_deep_nesting(container: str, below: list[dict], desired: list[dict], scope: str):
	"""Refuse a list that nests past the cap, in the rows the save keeps and the rows it leaves be."""
	# The type is the layer below's, not the client's, except for a row this level adds.
	# A row the client left out keeps its place.
	known = {item["key"]: item for item in below if item.get("key")}
	# Parents that are missing or loop are lifted first, as the save will lift them.
	kept = [
		{**item, "item_type": known[item["key"]].get("item_type")} if item["key"] in known else item
		for item in _orphans_lifted(_known(desired, known, scope), known)
	]
	named = {item["key"] for item in kept}
	left_out = [item for item in below if item.get("key") not in named]

	if past := nesting_errors(kept + left_out, container):
		frappe.throw(
			_("{0} is nested too deeply. A section holds items, and an item holds one more level.").format(
				frappe.bold(", ".join(past))
			),
			title=_("Nested Too Deeply"),
		)


def _sidebar_address(address: str, new_in: str = "", scope: str = "") -> tuple[str, str, str]:
	"""The app and the `(link_doctype, link_to)` pair behind a sidebar address; an own sidebar's is `("", key)`."""
	# Read from the standard record: unscrubbing is not a function, and an address no app
	# ships must be unarrangeable. An own key is read at the site layer or the person's own.
	if OWN_KEY.fullmatch(address):
		return _own_sidebar_address(address, new_in, scope)

	record = frappe.db.get_value(
		"Sidebar", {"name": address, "standard": 1}, ["app", "link_doctype", "link_to"], as_dict=True
	)

	if not record or not record.link_doctype:
		frappe.throw(_("{0} is not a sidebar this site ships.").format(address))

	return record.app, record.link_doctype, record.link_to


def _own_sidebar_address(key: str, new_in: str = "", scope: str = "") -> tuple[str, str, str]:
	owner = SITE_LAYER if key.startswith("site:") else frappe.session.user
	app = frappe.db.get_value("Sidebar", {"key": key, "standard": 0, "user": owner}, "app")

	# A level adds only its own: a person's `site:` key with no record stays unarrangeable.
	if not app and new_in and key.startswith(f"{scope}:"):
		app = new_in

	if not app:
		frappe.throw(_("{0} is not a sidebar you can arrange.").format(key))

	return app, "", key


def _is_site_administrator() -> bool:
	return frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles()


def _as_items(items: str | list) -> list[dict]:
	"""The client's list, whether the request carried it as a list or as a JSON string."""
	# A string that will not parse gets the same refusal as a non-list, not the decoder's 500.
	if isinstance(items, str):
		try:
			items = json.loads(items)
		except ValueError:
			items = None

	if not isinstance(items, list):
		frappe.throw(_("An arrangement is a list of items."), title=_("Not an Arrangement"))

	return [row for item in items if (row := _named(item))]


def _named(item) -> dict | None:
	"""One row of the client's list, or None if it does not name an item."""
	# A `parent_key` that is present but not a name drops the row instead of reading as top
	# level; blank means `None` or `""` only, since `0`, `[]` and `{}` are not the top level.
	if not isinstance(item, dict) or not _is_name(item.get("key")):
		return None

	parent = item.get("parent_key")
	if parent is not None and parent != "" and not _is_name(parent):
		return None

	return {**item, "parent_key": parent or None}


def _is_name(value) -> bool:
	return isinstance(value, str) and bool(value)


def _accounts_for(below: list[dict], desired: list[dict]) -> bool:
	"""Whether a submission names every row of the list it claims to arrange; membership, not difference."""
	named = {item["key"] for item in desired}

	return all(item["key"] in named for item in below if item.get("key"))


# The reduction


def reduce_arrangement(base: list[dict], desired: list[dict], scope: str) -> list[dict]:
	"""The whole ordered list a client is showing, as the smallest layer that produces it."""
	# A key the base does not hold is dropped, not refused: the app may have removed it while the
	# editor was open. Only the keys this scope adds are kept, whole, and capped before any walk.
	below = {item["key"]: item for item in base if item.get("key")}
	desired = _orphans_lifted(_known(desired, below, scope), below)
	anchors = anchors_for(base, desired)
	rows = []

	for item in desired:
		key = item["key"]
		row = _delta(item, below[key], anchors.get(key)) if key in below else _own(item, anchors.get(key))

		if row:
			rows.append(row)

	return rows


def _known(desired: list[dict], below: dict[str, dict], scope: str) -> list[dict]:
	"""The client's list, keeping the rows the layer below holds and the rows this level adds, each key once."""
	seen = set()
	kept = []
	added = 0

	for item in desired:
		key = item["key"]

		# The layer below may have deleted its own row while the editor was open: dropped, as a stale bare key is.
		if key not in below and key.startswith(f"{BELOW[scope]}:"):
			continue

		if key not in below and key.startswith(RESERVED_PREFIXES):
			_check_own_key(key, scope, seen)
		elif key not in below or key in seen:
			continue

		seen.add(key)
		kept.append(item)

		if key not in below:
			added += 1

		if added > OWN_ROWS_PER_CONTAINER:
			frappe.throw(
				_("You can add up to {0} items here.").format(OWN_ROWS_PER_CONTAINER),
				title=_("Too Many Items"),
			)

	return kept


def _check_own_key(key: str, scope: str, seen: set[str]):
	"""Refuse an own key of the wrong shape or level, or one the list already used."""
	if not OWN_KEY.fullmatch(key) or not key.startswith(f"{scope}:"):
		frappe.throw(
			_("{0} is not a key this level can add. It is {1}: and six lowercase letters or digits.").format(
				frappe.bold(key), scope
			),
			title=_("Not an Arrangement"),
		)

	if key in seen:
		frappe.throw(_("{0} is in this list twice.").format(frappe.bold(key)), title=_("Not an Arrangement"))


def _orphans_lifted(desired: list[dict], below: dict[str, dict]) -> list[dict]:
	"""An own row whose parent is not in the list, or whose parents lead back to it, goes to the top level."""
	parents = {item["key"]: item.get("parent_key") for item in desired}

	return [
		{**item, "parent_key": None}
		if item["key"] not in below
		and parents[item["key"]]
		and (parents[item["key"]] not in parents or _in_a_cycle(item["key"], parents))
		else item
		for item in desired
	]


def _in_a_cycle(key: str, parents: dict[str, str | None]) -> bool:
	seen = set()
	at = parents.get(key)

	while at and at not in seen:
		if at == key:
			return True
		seen.add(at)
		at = parents.get(at)

	return False


def _own(item: dict, anchors: list[dict] | None) -> dict:
	"""One row this level adds: the whole item, so nothing below it has to still hold it."""
	_check_own_content(item)

	row = {field: _scalar(item.get(field)) for field in OWN_FIELDS if field in item}
	row |= {"doctype": "Navigation Item", "added": 1}

	if isinstance(item.get("payload"), dict):
		row["payload"] = _compact_json(item["payload"])

	if anchors:
		row["anchors"] = json.dumps(anchors)
	else:
		row.pop("anchors", None)

	return row


def _compact_json(payload) -> str:
	"""The stored form of an object payload: as short as it goes, so a re-save keeps what a validator measured."""
	text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

	try:
		text.encode()
	except UnicodeEncodeError:  # a lone surrogate: only the escaped form is storable text
		return json.dumps(payload, separators=(",", ":"))

	return text


def _check_own_content(item: dict):
	"""Refuse an own row whose url opens anything but a path or an http(s) address, or whose payload is not an object."""
	url = item.get("url")
	payload = item.get("payload")

	if url and not (isinstance(url, str) and OWN_URL.fullmatch(url)):
		frappe.throw(
			_(
				"{0} is not a link this item can open. Use a path on this site, or an http or https address."
			).format(frappe.bold(str(url)[:140])),
			title=_("Not an Arrangement"),
		)

	if isinstance(payload, str) and payload:
		try:
			payload = json.loads(payload)
		except ValueError:
			pass

	if payload and not isinstance(payload, dict):
		frappe.throw(
			_("The payload of {0} is not an object.").format(frappe.bold(item["key"])),
			title=_("Not an Arrangement"),
		)


def _delta(item: dict, below: dict, anchors: list[dict] | None) -> dict | None:
	"""One row, or None when this item is exactly what the layer below already resolves to."""
	overrides = [field for field in OVERRIDABLE if _differs(item.get(field), below.get(field))]
	hidden = int(bool(item.get("hidden")))

	if not overrides and not anchors and hidden == int(bool(below.get("hidden"))):
		return None

	row = {"doctype": "Navigation Item", "key": item["key"], "hidden": hidden}

	if overrides:
		# The fieldnames are stored beside the values: that is what lets a person blank a label
		# the app shipped, which "whatever is non-blank" cannot express.
		row["overrides"] = json.dumps(overrides)
		row.update({field: _scalar(item.get(field)) for field in overrides})

	if anchors:
		row["anchors"] = json.dumps(anchors)

	return row


def _scalar(value):
	"""One overridden value as a `Data` or `Check` column can hold it; a list or object reads as blank."""
	return value if isinstance(value, str | int | float | bool) or value is None else None


def _differs(sent, resolved) -> bool:
	"""Whether the client changed a field, treating a blank and a missing one as the same thing."""
	# The resolved list omits blank fields, but a cleared one comes back as `""`.
	return (_scalar(sent) or None) != (resolved or None)


def anchors_for(base: list[dict], desired: list[dict]) -> dict[str, list[dict]]:
	"""One anchor for each row that has to move, and nothing for the rows that do not."""
	# Order is compared per parent, and the rows to move are those outside the longest common
	# subsequence; each anchors after its predecessor in the desired list.

	# A row at the front of its group anchors before the first following row that is not
	# itself moving: naming a row yet to move would place it against a position about to change.
	base_groups = _siblings(base)
	anchors: dict[str, list[dict]] = {}

	for parent, keys in _siblings(desired).items():
		staying = _longest_common(base_groups.get(parent, []), keys)
		moving = [key for key in keys if key not in staying]

		for key in moving:
			index = keys.index(key)

			if index:
				anchors[key] = [{"after": keys[index - 1]}]
				continue

			ahead = next((other for other in keys[1:] if other in staying), None)
			if ahead:
				anchors[key] = [{"before": ahead}]
			elif parent:
				anchors[key] = [{"parent_key": parent}]

	return anchors


def _siblings(items: list[dict]) -> dict[str | None, list[str]]:
	"""The keys under each parent, in order. `None` is the top level."""
	groups: dict[str | None, list[str]] = {}

	for item in items:
		if item.get("key"):
			groups.setdefault(item.get("parent_key") or None, []).append(item["key"])

	return groups


def _longest_common(before: list[str], after: list[str]) -> set[str]:
	"""The largest set of keys that can keep their relative order, so the fewest rows move."""
	# Quadratic, but over one parent's children on a save, not in boot.
	rows, columns = len(before), len(after)
	lengths = [[0] * (columns + 1) for _ in range(rows + 1)]

	for i in range(rows - 1, -1, -1):
		for j in range(columns - 1, -1, -1):
			if before[i] == after[j]:
				lengths[i][j] = lengths[i + 1][j + 1] + 1
			else:
				lengths[i][j] = max(lengths[i + 1][j], lengths[i][j + 1])

	common: set[str] = set()
	i = j = 0

	while i < rows and j < columns:
		if before[i] == after[j]:
			common.add(before[i])
			i, j = i + 1, j + 1
		elif lengths[i + 1][j] >= lengths[i][j + 1]:
			i += 1
		else:
			j += 1

	return common


# The stored layer


def _existing(target: Target) -> str | None:
	"""The name of the record this layer is stored in, if it has one."""
	address = {field: value for field, value in target.layer.items() if field != "doctype"}

	return frappe.db.get_value(target.layer["doctype"], address)


def _write(target: Target, rows: list[dict]):
	"""Put these rows in this layer, and delete the layer when there are none."""
	# An empty layer and no layer resolve identically, so keeping one is a row that means nothing.
	# A rail layer that sets a navigation layout is not empty: it stays, row-less.
	# `ignore_permissions`: the gate is the endpoint's; both containers give a Desk User no write.
	doctype = target.layer["doctype"]
	doc = _locked(target)

	if not rows and not doc.get("navigation_layout"):
		_delete(doc)
		return

	doc.set(ITEMS_FIELD[doctype], rows)
	doc.save(ignore_permissions=True)


def _write_layout(target: Target, navigation_layout: str):
	"""Put the navigation layout on this level's rail, and drop the record when it ends up empty."""
	doc = _locked(target)

	if not navigation_layout and not doc.items:
		_delete(doc)
		return

	doc.navigation_layout = navigation_layout
	doc.save(ignore_permissions=True)


def _delete(doc: Document):
	"""Drop a stored layer; a layer never saved has nothing to drop."""
	if not doc.is_new():
		frappe.delete_doc(doc.doctype, doc.name, ignore_permissions=True, delete_permanently=True)


def _locked(target: Target) -> Document:
	"""The stored layer, row-locked until the request commits so an empty check cannot go stale."""
	address = {field: value for field, value in target.layer.items() if field != "doctype"}
	existing = frappe.db.get_value(target.layer["doctype"], address)

	if existing:
		return frappe.get_doc(target.layer["doctype"], existing, for_update=True)

	return frappe.get_doc(dict(target.layer))
