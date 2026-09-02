# ARRANGEMENT — the three endpoints a person's navigation edits go through.
#
# #42363 settled the rules; this is them. Desk v2's client has never persisted any user state,
# so these are its first write that is not a document save, and the shape they take is the one
# thing everything else on this surface has to agree with.
#
# The one idea underneath: **a move is an anchor, not a position.** A person who drags Contacts
# above Deals has said "Contacts goes before Deals", not "Contacts is item 3" — and those two
# stop meaning the same thing the moment the app ships a ninth item. So a saved layer names the
# rows that moved and says what each moved next to, and everything nobody touched keeps the
# position the layer below it gave it. It is the same anchor an app writes to insert its rows
# into another app's rail (#42364), one phase later and against a list the writer *can* see.
#
# What crosses the wire is not that, though. The client sends **the whole ordered arrangement it
# is showing**, which is desk v1's shape, and the server reduces it here. That division is
# deliberate: a client that sent anchors would be computing identity and difference against a
# base it holds a stale copy of, which is the mistake v1 made in the other direction — its
# sidebar manager recomputes the server's item key in JS and gets it wrong two ways
# (`sidebar_manager.js:294-298`).
#
# Three endpoints, against desk v1's twelve. V1 spends four on overlay writes, five on resets and
# three on layer reads, and the multiplication is one word — `dock` or `sidebar`, `user` or
# `site` — baked into each name. Here that word is an argument. Two of v1's resets are not
# ported at all: `reset_dock_for_everyone` and `reset_to_standard` each delete the site layer
# *and every user's* from one call, and a blast radius that large belongs to a considered
# administrative action rather than to a button on a rail.

import json
from collections.abc import Callable
from functools import partial
from typing import NamedTuple

import frappe
from frappe import _

from .navigation import SITE_LAYER, resolve_navigation, resolve_rail, resolve_sidebar
from .navigation_filter import NavigationContext
from .permissions import has_app_permission

# The two containers, and what each needs to find or write a layer. `field` is the table the
# rows live in: `Sidebar` holds desk v1's `items` beside desk v2's `navigation_items`, so naming
# the parentfield is what keeps a v2 write from landing in v1's sidebar.
CONTAINERS = ("Rail", "Sidebar")
ITEMS_FIELD = {"Rail": "items", "Sidebar": "navigation_items"}

# A scope, and the scope whose resolved list a save at that scope is relative to. A person's
# anchors are written against what they were shown, which is the site's arrangement; the site's
# are written against what the apps ship.
SCOPES = ("user", "site")
BELOW = {"user": "site", "site": "base"}

# What a delta row may have an opinion about. Presentation only: an arrangement changes how an
# item reads and where it sits, never what it opens, because a row that could repoint its own
# destination would let a person's layer turn an item into a different item under the same key —
# and the key is what every other layer's edits are filed against (#42229).
#
# `parent_key` is not here on purpose. Reparenting travels as an anchor, since `after` and
# `before` already carry the parent of the row they name: beside means beside, and a column that
# said one thing while the anchor said another would need a precedence rule nobody would
# remember.
OVERRIDABLE = ("label", "icon", "collapsible", "keep_closed")


@frappe.whitelist()
def get_arrangement(container: str, address: str, scope: str = "user") -> list[dict]:
	"""The list to arrange: resolved up to and including `scope`, hidden rows kept.

	Hidden rows are the reason this is not just `boot.navigation`. Boot drops them, because the
	browser cannot render a row it must not show — but an editor that dropped them would be an
	editor in which hiding is a one-way door, and the whole point of a hide is that the person
	who made it can take it back.
	"""
	return _target(container, address, scope).resolve(upto=scope, keep_hidden=True)


@frappe.whitelist()
def save_arrangement(container: str, address: str, items: str | list, scope: str = "user") -> dict:
	"""Store one layer's arrangement and hand back the whole prefix's navigation.

	`items` is the entire ordered list the client is showing, hidden rows included. What gets
	stored is the difference between that and the list one scope below: the rows that moved, the
	rows whose label or icon was changed, and the rows whose hidden flag differs. A row with
	nothing to say is not written, so dragging an item away and back leaves no trace.

	The return is `{rail, sidebars}` for the whole prefix rather than the one list that changed,
	and the client swaps it into `boot.navigation` wholesale. That is v1's pattern and it is
	affordable for the reason #42362 measured: the framework's own prefix resolves in 8-25 ms
	warm at 20,618 B. It is also the only answer that stays correct — hiding a rail item of type
	`Sidebar` changes which sidebars are reachable, so a response scoped to the list that was
	written would be a half-truth the client had no way to notice.
	"""
	target = _target(container, address, scope)
	below = target.resolve(upto=BELOW[scope], keep_hidden=True)
	desired = _as_items(items)

	rows = reduce_arrangement(below, desired)

	# Deleting is spelled the same way here as saving nothing, and that is deliberate: an empty
	# reduction drops the layer, which is what keeps "drag it away and back" and "reset" from
	# ending in two states that only look alike. It also means the one place a save can turn into
	# a reset is this one, so it is the only place that has to be sure.
	#
	# It is sure when the submission **accounted for the whole list below**. The client is always
	# showing that list, so a save that names every row of it and still reduces to nothing has
	# genuinely said "this matches" -- while one that names only part of it has said nothing about
	# the rest, and reading that as "delete everything" is a statement it did not make. Three
	# separate ways of arriving at an empty reduction fall under this: a body where every row was
	# malformed, one whose keys the list no longer holds, and one that keeps a single unchanged
	# row and drops the others.
	#
	# The completeness test is only on this path on purpose. A save that *does* write rows is
	# allowed to be incomplete, because rows nobody mentioned keeping the position the layer below
	# gave them is the whole design -- and `reduce_arrangement` already drops an unknown key
	# rather than refusing the save it came in, for the same reason. Missing rows only change the
	# outcome catastrophically when the answer is delete.
	if below and not rows and not _accounts_for(below, desired):
		frappe.throw(
			_(
				"This arrangement does not cover everything {0} is showing, so it cannot be saved as one. Reload it, or reset it to go back to how it arrived."
			).format(frappe.bold(target.app)),
			title=_("Not an Arrangement"),
		)

	_write(target, rows)

	return resolve_navigation(target.app)


@frappe.whitelist()
def reset_arrangement(container: str, address: str, scope: str = "user") -> dict:
	"""Delete one layer and hand back what the prefix resolves to without it.

	One layer, named by the same three arguments a save takes. Resetting your own rail cannot
	reach the site's, and resetting the site's cannot reach anybody's.
	"""
	target = _target(container, address, scope)

	_write(target, [])

	return resolve_navigation(target.app)


# Addressing and the gate


class Target(NamedTuple):
	"""One addressed layer: whose app it is, how to resolve it, and where it is stored.

	The three travel together because each of the endpoints needs all three, and because
	resolving a sidebar address costs a query — one that would otherwise be paid twice on a save,
	once to gate the request and once to find the record to write.
	"""

	app: str
	resolve: Callable[..., list[dict]]
	layer: dict


def _target(container: str, address: str, scope: str) -> Target:
	"""Check the arguments and the caller, and describe the layer they name.

	The gate is `has_app_permission` on the addressed app, plus `System Manager` for the site
	scope (#42354). Unlike the reads this gate is the boundary rather than a choice of error
	page: no doctype permission stands behind arranging the rail of an app you may not enter, so
	there is nothing further along to refuse a request this one lets through.

	There is deliberately no `user` argument anywhere in this module. The user scope is the
	session user and can be nothing else, so "write somebody else's arrangement" is not a request
	that can be made and does not need refusing.
	"""
	# Explicitly, not on the annotations alone. `validate_argument_types` only applies inside a
	# request or a test, and Frappe accepts complex values throughout — so a parameter expected
	# to be a string can arrive as a filter list, and `address` is read straight into a
	# `get_value` filter below. `{"name": ["!=", ""]}` is a whole different query from
	# `{"name": "..."}`, and the difference is invisible at the call site.
	if not all(isinstance(argument, str) for argument in (container, address, scope)):
		frappe.throw(_("A container, an address and a scope are each one name."))

	if container not in CONTAINERS:
		frappe.throw(_("{0} is not a navigation container.").format(container))

	if scope not in SCOPES:
		frappe.throw(_("{0} is not an arrangement scope.").format(scope))

	# `standard: 0` is in the stored address because an app's own layer and the site's
	# arrangement of it are two records at one address, and resetting the site's must never reach
	# the app's.
	stored = {"user": frappe.session.user if scope == "user" else SITE_LAYER, "standard": 0}

	# The one deliberate bypass of the permission filter (#42231 decision 12), and it is the
	# **site** scope that earns it: a manager arranging the site's navigation is arranging it for
	# everybody, so a list filtered down to what they personally may see would let them delete
	# other people's items by saving a list those items were never on. It stays off at user
	# scope, where the person is arranging their own list and showing them rows they may not see
	# would be a leak with nothing to buy it.
	#
	# It is set once, here, so the read and the reduce base a save is computed against are always
	# filtered the same way. A save whose `below` held rows the editor never showed would anchor
	# moves against a list the client was not looking at.
	check_permission = scope != "site"

	if container == "Rail":
		app = address
		resolve = partial(resolve_rail, app, check_permission=check_permission)
		stored |= {"app": app, "extends": ""}
	else:
		app, link_doctype, link_to = _sidebar_address(address)
		resolve = partial(resolve_sidebar, link_doctype, link_to, check_permission=check_permission)
		stored |= {"app": app, "link_doctype": link_doctype, "link_to": link_to}

		# A sidebar this person's blocked module takes away resolves to nothing, and a save
		# against nothing is a **delete**: the reduction drops every submitted row and `_write`
		# reads an empty one as "drop the layer". So an editor still open when the block landed
		# would quietly destroy an arrangement its owner cannot see to rebuild. Refused rather
		# than special-cased in the reducer, because the honest answer to "arrange this" is that
		# there is no longer a list to arrange. Site scope bypasses this with the rest of the
		# filter, since the block is one person's and the site's list is everybody's.
		if check_permission and not NavigationContext("").address_is_offered(link_doctype, link_to):
			frappe.throw(
				_("{0} is not available to you, so there is nothing here to arrange.").format(
					frappe.bold(link_to)
				),
				title=_("Nothing to Arrange"),
			)

	# Before the gate, because `has_app_permission` falls back to "is a System User" for an app
	# that declares no `app_permission` hook -- and an app that is not on the bench declares
	# nothing, so an unknown name would pass a check it was never actually subject to.
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
	"""The app and the `(link_doctype, link_to)` pair behind a scrubbed sidebar address.

	The client holds the scrubbed address and nothing else — it is the key `boot.navigation`
	uses and the string a rail item of type `Sidebar` carries in `link_to` — and unscrubbing is
	not a function: `module_def_accounts_receivable` could be two different modules. So the pair
	is read back from the standard record, whose name #42355 made the scrubbed address for
	exactly this kind of reason.

	Reading it from the *standard* record also settles which app is being arranged, and makes an
	address no app ships unarrangeable — which is #42229's rule about deltas over nothing being
	inert, applied one step earlier so a person gets a refusal rather than a row that resolves to
	nothing.
	"""
	record = frappe.db.get_value(
		"Sidebar", {"name": address, "standard": 1}, ["app", "link_doctype", "link_to"], as_dict=True
	)

	if not record or not record.link_doctype:
		frappe.throw(_("{0} is not a sidebar this site ships.").format(address))

	return record.app, record.link_doctype, record.link_to


def _is_site_administrator() -> bool:
	return frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles()


def _as_items(items: str | list) -> list[dict]:
	"""The client's list, however the request encoded it.

	`frappe.whitelist` hands a JSON body through as a list and a form post as a string, and both
	reach this endpoint — the client sends JSON, and a test or a `bench execute` passes the list
	itself.

	A string that will not parse is refused with the same message as a body that is not a list,
	rather than raising the decoder's own error: both mean the caller sent something this is not,
	and a `JSONDecodeError` off a whitelisted method is a 500 where the caller needs a sentence.

	What comes back is rows whose `key` and `parent_key` are names, because both are read as
	dictionary keys from here on. A list is not hashable, so one arriving in either column would
	end a whitelisted save in an uncaught `TypeError` rather than in an answer. The row is
	dropped rather than the request refused, for the reason `reduce_arrangement` drops an
	unknown key: the rest of the arrangement is still what the person meant.
	"""
	if isinstance(items, str):
		try:
			items = json.loads(items)
		except ValueError:
			items = None

	if not isinstance(items, list):
		frappe.throw(_("An arrangement is a list of items."), title=_("Not an Arrangement"))

	return [row for item in items if (row := _named(item))]


def _named(item) -> dict | None:
	"""One row of the client's list, or None if it does not name an item.

	A `parent_key` that is *blank* is the top level and is the ordinary case. A `parent_key` that
	is present but is not a name drops the whole row, rather than being read as blank: reading it
	as blank would say the row belongs at the top level, which is a placement nobody asked for
	and one the reduction would faithfully write down. Dropping the row says nothing about it
	instead, so it stays exactly where the layer below put it.

	Blank means `None` or `""` and nothing else. A truthiness test would let the *falsy*
	non-names through -- `0`, `false`, `[]`, `{}` -- and then read each of them as the top level,
	which is the very reparenting this exists to refuse.
	"""
	if not isinstance(item, dict) or not _is_name(item.get("key")):
		return None

	parent = item.get("parent_key")
	if parent is not None and parent != "" and not _is_name(parent):
		return None

	return {**item, "parent_key": parent or None}


def _is_name(value) -> bool:
	return isinstance(value, str) and bool(value)


def _accounts_for(below: list[dict], desired: list[dict]) -> bool:
	"""Whether a submission names every row of the list it claims to be an arrangement of.

	Membership only, never difference: a full list that happens to differ in nothing names every
	row of it, and that is the ordinary save whose layer goes.
	"""
	named = {item["key"] for item in desired}

	return all(item["key"] in named for item in below if item.get("key"))


# The reduction


def reduce_arrangement(base: list[dict], desired: list[dict]) -> list[dict]:
	"""The whole ordered list a client is showing, as the smallest layer that produces it.

	Every row written here says something the list below does not already say. That is what
	makes an app's later change reach a person who has arranged their rail: a layer that recorded
	every position would pin the whole list, and the ninth item an app ships would have nowhere
	to land.

	A key the base does not hold is **dropped**, not written and not refused. The case is
	ordinary rather than exceptional — an app removed an item while somebody had the editor
	open — and the two alternatives are both worse than dropping it: refusing loses the rest of a
	save over a row the person never touched, and writing it would author an item into a layer
	from values a browser supplied, under a key an app may later ship for something else.
	Authoring new items into a layer is nobody's yet; the editor cannot make one, and every
	arrangement it sends is of rows that came from the server.

	Dropping those rows **first** is also what bounds the work. `anchors_for` compares two
	orders with a longest-common-subsequence table, which is quadratic in the length of a
	parent's list — fine for the 194 rows a real prefix resolves to, and not fine for a request
	body that repeats one key ten thousand times. After this filter the list is at most the
	base's length whatever the client sent, so the cost is a property of the site's navigation
	rather than of the request.
	"""
	below = {item["key"]: item for item in base if item.get("key")}
	desired = _known(desired, below)
	anchors = anchors_for(base, desired)

	return [row for item in desired if (row := _delta(item, below[item["key"]], anchors.get(item["key"])))]


def _known(desired: list[dict], below: dict[str, dict]) -> list[dict]:
	"""The client's list, keeping only rows the layer below holds, and each key only once.

	A key sent twice keeps its **first** position, which is the answer `apply_layer` already
	gives when a stored layer names one entry twice: the alternative is rendering it twice.
	"""
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
		# The fieldnames are stored beside the values on purpose. An explicit list is what lets a
		# person blank a label the app shipped, which "whatever is non-blank" cannot express, and
		# it is what makes "did a human choose this" answerable at render time (#42229).
		row["overrides"] = json.dumps(overrides)
		row.update({field: _scalar(item.get(field)) for field in overrides})

	if anchors:
		row["anchors"] = json.dumps(anchors)

	return row


def _scalar(value):
	"""One overridden value, as something a `Data` or `Check` column can hold.

	The rows come off a request body, so a field can arrive as a list or an object where a
	string was expected. Every overridable field is a scalar, so anything that is not one is
	read as blank rather than handed to the database to interpret — this is the same reasoning
	as the type annotations on the endpoints, applied one level down, where the annotation
	cannot reach.
	"""
	return value if isinstance(value, str | int | float | bool) or value is None else None


def _differs(sent, resolved) -> bool:
	"""Whether the client changed a field, treating a blank and a missing one as the same thing.

	The resolved list omits blank fields rather than sending `null`, so a field the person never
	touched comes back as absent where it went out as absent — but a field they *cleared* comes
	back as `""`. Those two have to be one value here, or clearing an already-blank label would
	write a row saying nothing.
	"""
	return (_scalar(sent) or None) != (resolved or None)


def anchors_for(base: list[dict], desired: list[dict]) -> dict[str, list[dict]]:
	"""One anchor for each row that has to move, and nothing for the rows that do not.

	Several sets of anchors describe the same list, so this picks one rule and it is written
	here. **Order is compared per parent**, because the payload is a flat list the client renders
	as a tree, and where a section's children sit relative to another section's is not something
	anybody can see or intend. Within one parent, the rows to move are the ones outside the
	longest common subsequence of the two orders — the largest set that can stay put — and each
	one is anchored **after the row that precedes it in the list the person is looking at**.

	Anchors are resolved in the order the layer's rows are written, which is the order of
	`desired`, and that is what makes anchoring backwards safe: by the time a row is placed, the
	row it names is already where it is going to be. The exception is a row that moved to the
	front of its group, which has no predecessor. It anchors *before* the first following row
	that is **not** itself moving, for the same reason — naming a row that has yet to move would
	place it against a position that is about to change.

	A row alone under a parent, with nothing on either side to name, anchors to the parent
	itself. At the top level there is no such fallback and none is needed: a list of one is in
	order whatever anybody says.
	"""
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
	"""The largest set of keys that can keep their relative order, so the fewest rows move.

	An ordinary longest-common-subsequence table. Both lists are one parent's children, which is
	a handful of rows on any real navigation and cannot be otherwise: this runs on a save, not in
	boot, and the quadratic cost is measured against a person having dragged something.
	"""
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
	"""Put these rows in this layer, and delete the layer when there are none.

	An empty layer and no layer resolve identically -- `apply_layer` returns the list unchanged
	for a layer that named nothing -- so keeping one would be a row that means nothing, and
	deleting it is what makes "arrange it back the way it was" and "reset" end in the same state
	rather than in two states that only look alike.

	`ignore_permissions`, because the gate is the endpoint's. Both containers' `has_permission`
	hooks give a `Desk User` read and no write at all, which is what stops one person reading
	another's layer through the API; a person arranging their own rail needs no write permission
	on a table they can never write directly.
	"""
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
