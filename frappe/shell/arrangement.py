# ARRANGEMENT — the three endpoints a person's navigation edits go through.

# A move is an anchor, not a position: a saved layer names the rows that moved and what each
# moved next to, so an item the app ships later still has somewhere to land.

# The client sends the whole ordered list it is showing and the server reduces it; a client
# that sent anchors would be diffing against a base it holds a stale copy of.

import json
from collections.abc import Callable
from functools import partial
from typing import NamedTuple

import frappe
from frappe import _

from .navigation import SITE_LAYER, resolve_navigation, resolve_rail, resolve_sidebar
from .navigation_filter import NavigationContext
from .permissions import has_app_permission

# `Sidebar` holds desk v1's `items` beside desk v2's `navigation_items`; naming the
# parentfield keeps a v2 write out of v1's sidebar.
CONTAINERS = ("Rail", "Sidebar")
ITEMS_FIELD = {"Rail": "items", "Sidebar": "navigation_items"}

# A scope, and the scope whose resolved list a save at that scope is relative to.
SCOPES = ("user", "site")
BELOW = {"user": "site", "site": "base"}

# Presentation only: an arrangement never changes what an item opens. `parent_key` is
# not here; reparenting travels as an anchor, whose `after`/`before` carry the parent.
OVERRIDABLE = ("label", "icon", "collapsible", "keep_closed")


@frappe.whitelist()
def get_arrangement(container: str, address: str, scope: str = "user") -> list[dict]:
	"""The list to arrange: resolved up to and including `scope`, hidden rows kept."""
	# Hidden rows stay, or hiding would be a one-way door.
	return _target(container, address, scope).resolve(upto=scope, keep_hidden=True)


@frappe.whitelist()
def save_arrangement(container: str, address: str, items: str | list, scope: str = "user") -> dict:
	"""Store one layer's arrangement and hand back the whole prefix's navigation."""
	target = _target(container, address, scope)
	below = target.resolve(upto=BELOW[scope], keep_hidden=True)
	desired = _as_items(items)

	rows = reduce_arrangement(below, desired)

	# An empty reduction drops the layer, so this is the one place a save can become a reset.
	# It may only do so when the submission accounted for the whole list below.
	if below and not rows and not _accounts_for(below, desired):
		frappe.throw(
			_(
				"This arrangement does not cover everything {0} is showing, so it cannot be saved as one. Reload it, or reset it to go back to how it arrived."
			).format(frappe.bold(target.app)),
			title=_("Not an Arrangement"),
		)

	_write(target, rows)

	# The whole prefix comes back: hiding a rail item of type `Sidebar` changes which sidebars
	# are reachable, so a response scoped to the one list would be a half-truth.

	return resolve_navigation(target.app)


@frappe.whitelist()
def reset_arrangement(container: str, address: str, scope: str = "user") -> dict:
	"""Delete one layer and hand back what the prefix resolves to without it."""
	target = _target(container, address, scope)

	_write(target, [])

	return resolve_navigation(target.app)


# Addressing and the gate


class Target(NamedTuple):
	"""One addressed layer: whose app it is, how to resolve it, and where it is stored."""

	app: str
	resolve: Callable[..., list[dict]]
	layer: dict


def _target(container: str, address: str, scope: str) -> Target:
	"""Check the arguments and the caller, and describe the layer they name."""
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
		app, link_doctype, link_to = _sidebar_address(address)
		resolve = partial(resolve_sidebar, link_doctype, link_to, check_permission=check_permission)
		stored |= {"app": app, "link_doctype": link_doctype, "link_to": link_to}

		# A sidebar this person's blocked module removes resolves to nothing, and a save against
		# nothing is a delete; refuse it instead.
		if check_permission and not NavigationContext("").address_is_offered(link_doctype, link_to):
			frappe.throw(
				_("{0} is not available to you, so there is nothing here to arrange.").format(
					frappe.bold(link_to)
				),
				title=_("Nothing to Arrange"),
			)

	# Before the gate: `has_app_permission` falls back to "is a System User" for an app with
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


def _sidebar_address(address: str) -> tuple[str, str, str]:
	"""The app and the `(link_doctype, link_to)` pair behind a scrubbed sidebar address."""
	# Read from the standard record: unscrubbing is not a function, and an address no app
	# ships must be unarrangeable.
	record = frappe.db.get_value(
		"Sidebar", {"name": address, "standard": 1}, ["app", "link_doctype", "link_to"], as_dict=True
	)

	if not record or not record.link_doctype:
		frappe.throw(_("{0} is not a sidebar this site ships.").format(address))

	return record.app, record.link_doctype, record.link_to


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
	# A `parent_key` that is present but not a name drops the row rather than reading as top
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


def reduce_arrangement(base: list[dict], desired: list[dict]) -> list[dict]:
	"""The whole ordered list a client is showing, as the smallest layer that produces it."""
	# A key the base does not hold is dropped, not refused: the app may have removed it while
	# the editor was open. Dropping first also bounds `anchors_for` to the base's length.
	below = {item["key"]: item for item in base if item.get("key")}
	desired = _known(desired, below)
	anchors = anchors_for(base, desired)

	return [row for item in desired if (row := _delta(item, below[item["key"]], anchors.get(item["key"])))]


def _known(desired: list[dict], below: dict[str, dict]) -> list[dict]:
	"""The client's list, keeping only rows the layer below holds, and each key once (first wins)."""
	seen = set()
	kept = []

	for item in desired:
		key = item["key"]
		if key in below and key not in seen:
			seen.add(key)
			kept.append(item)

	return kept


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


def _write(target: Target, rows: list[dict]):
	"""Put these rows in this layer, and delete the layer when there are none."""
	# An empty layer and no layer resolve identically, so keeping one is a row that means nothing.
	# `ignore_permissions`: the gate is the endpoint's; both containers give a Desk User no write.
	doctype = target.layer["doctype"]
	address = {field: value for field, value in target.layer.items() if field != "doctype"}
	existing = frappe.db.get_value(doctype, address)

	if not rows:
		if existing:
			frappe.delete_doc(doctype, existing, ignore_permissions=True, delete_permanently=True)
		return

	doc = frappe.get_doc(doctype, existing) if existing else frappe.get_doc(dict(target.layer))
	doc.set(ITEMS_FIELD[doctype], rows)
	doc.save(ignore_permissions=True)
