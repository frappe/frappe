# NAVIGATION — the rail and the sidebars of one prefix, resolved for one user.
#
# #42356: resolution spans both containers, so it belongs to neither controller. It cannot
# live on `Sidebar` either, whose class is desk v1's `Sidebar(Document, DeskViews)` — v1's
# boot builder — and hanging desk v2's resolution off that would couple the new path to the
# old one on its first day. It lives beside its only caller instead, `shell/boot.py`, since
# #42232 made navigation a framework boot key.
#
# One entry point. #42232 decided the server sends one resolved tree that the browser never
# restacks, so composing the payload is this module's job and not the caller's — the moment a
# second caller appears (the overlay write endpoints, #42363) it would compose it slightly
# differently.
#
# Nothing here is whitelisted. `get_boot` has already checked the prefix registry and
# `has_app_permission` before it composes any key, so a second trust boundary inside the
# resolver would duplicate a check no caller can skip. Desk v1 does the same: `resolve_dock`
# and `resolve_sidebar` are both unwhitelisted with one caller each.

import json
from urllib.parse import quote

import frappe
from frappe.desk.layers import resolve_layers

from .extensions import extend

# What a stored row carries. Read as columns rather than as a document, because `Sidebar`'s
# document is desk v1's: the class subclasses `DeskViews` and the record holds v1's `items`
# beside desk v2's `navigation_items`, so a `get_doc` here would put v1's rows one attribute
# away from the ones we want.
ITEM_FIELDS = (
	"key",
	"parent_key",
	"item_type",
	"link_doctype",
	"link_to",
	"url",
	"payload",
	"label",
	"icon",
	"collapsible",
	"keep_closed",
	"hidden",
	"added",
	"overrides",
	# Read for the extension merge, not for the browser. `anchors` is consumed there and
	# `switches_app` becomes a `url` on the way out — but both are in this list rather than
	# read separately, because `overrides` may name any field a layer has an opinion about,
	# and a site turning a contributed item's app-switching off is exactly such an opinion.
	"anchors",
	"switches_app",
)

# What reaches the browser. `hidden`, `added` and `overrides` are how a layer was *stored*;
# once the layers are merged they say nothing about the item on screen, and #42232's payload
# is for rendering.
WIRE_FIELDS = (
	"key",
	"parent_key",
	"item_type",
	"link_doctype",
	"link_to",
	"url",
	"payload",
	"label",
	"icon",
	"collapsible",
	"keep_closed",
)

# `Rail.SITE_LAYER` and `Sidebar.SITE_LAYER`, which are both the empty string for the same
# reason: one spelling of "not a person's own layer" has to reach the unique index.
SITE_LAYER = ""

# `Rail.NO_HOST`, and the same empty string for the same reason: an app's own rail extends
# nobody, and one spelling of that has to reach the unique index — and this filter.
NO_HOST = ""

# #42231's bucket for a kind whose destination is a doctype, and the one bucket this module
# applies. The other five are #42233's, along with every authored row that is not contributed.
READABLE_DOCTYPE = "Readable DocType"


def resolve_navigation(app: str) -> dict:
	"""The whole navigation payload for one prefix, as the session user sees it.

	`{"rail": [...], "sidebars": {address: [...]}}` — the rail plus *every* sidebar in the
	prefix, because #42232 decided no rail click may cost a request.

	The sidebars are keyed by their **scrubbed address**, not by the name of any record. A
	resolved sidebar is the merge of up to three rows with three different names: #42355 names a
	standard row after its address and hash-names the site and user layers, so no one row's name
	identifies the sidebar. The address is what all three share, and for a shipped sidebar the
	scrubbed address is byte-identical to the standard row's name — which is the string a rail
	item of type `Sidebar` already carries in `link_to`, so the browser still does one dictionary
	lookup on a value it is holding.
	"""
	return {"rail": resolve_rail(app), "sidebars": _resolve_sidebars(app)}


def resolve_rail(app: str, *, upto: str = "user", keep_hidden: bool = False) -> list[dict]:
	"""One app's rail: its own layer plus what other apps add to it, then the site's, then this user's.

	`upto` stops the stack short, and `keep_hidden` leaves the hidden rows in. Both are the
	arrangement editor's (#42363): it reads at the scope it writes, hidden rows and all, because
	otherwise nothing a person hid could ever be unhidden, and it reads one scope lower to find
	the list a person's moves are anchored against.

	Extension happens to the *base*, before the site and user layers are laid over it. That is
	what makes a person's arrangement of a host rail one row rather than one row per extending
	app: they are shown one list and they arrange one list (#42364).

	When the app ships no `Rail` record the base is *derived* from the address table, and it goes
	through the same merge as any other base rather than short-circuiting past it. That is not a
	corner case: no app ships a `Rail` record today, so every app takes this path until the
	walking skeleton (#42233) converts one. Short-circuiting would make the per-user overlay
	(#42230) work on converted apps only, so whether a person may reorder their own rail would
	depend on something they cannot see.
	"""
	layers = _rail_layers(app)
	base = layers.pop("standard", None)
	# A derived base's keys are doctype names nobody authored, so an anchor may not name one
	# (#42364). The flag is computed here rather than inside the merge because this is the only
	# line that knows which of the two bases it is holding.
	shipped = base is not None
	if base is None:
		base = _derive_rail(app)

	base = extend(base, _rail_contributions(app), anchorable=shipped)

	return _merge(base, _upto(layers, upto), keep_hidden=keep_hidden)


def _resolve_sidebars(app: str) -> dict[str, list[dict]]:
	"""Every sidebar this app ships, resolved and keyed by scrubbed address.

	Empty until an app ships rows, and deliberately so: derivation produces a rail and nothing
	else (#42356). A derived *doctype* sidebar would be saved views, which this map put out of
	scope, and deriving only *module* sidebars would make the fallback behave differently for a
	doctype-primary app and a module-primary one — the asymmetry charter point 2 exists to
	prevent. #42357 confirmed it from the other side: desk v2's one module-contents computation
	yields doctypes, which is the module *page's* list, and the module page and the module
	sidebar are two lists on purpose.
	"""
	addresses = _sidebar_addresses(app)
	if not addresses:
		return {}

	layers = _sidebar_layers(addresses)
	resolved = {}

	for address in addresses:
		by_layer = layers.get(address, {})
		base = by_layer.get("standard", [])
		items = _merge(base, _upto(by_layer, "user"))
		if items:
			# An address that resolves to nothing is absent rather than empty. The payload is read
			# by key, so the two mean the same thing to the browser, and a linked rail item whose
			# sidebar has no rows renders as an independent one (#42357).
			resolved[frappe.scrub(f"{address[0]} {address[1]}")] = items

	return resolved


def resolve_sidebar(
	link_doctype: str, link_to: str, *, upto: str = "user", keep_hidden: bool = False
) -> list[dict]:
	"""One sidebar at one address, for a caller that wants that one and not the prefix.

	Boot resolves every sidebar in the prefix in one pair of queries, because a modular app has
	one per module and per-address reads would put two queries per module into the blocking
	pre-mount path. The arrangement editor is the other kind of caller: it is holding one sidebar
	and paying one request for it, so it reads that one.
	"""
	by_layer = _sidebar_layers([(link_doctype, link_to)]).get((link_doctype, link_to), {})

	return _merge(by_layer.get("standard", []), _upto(by_layer, upto), keep_hidden=keep_hidden)


# The layers a resolution stacks, in order, up to and including the scope asked for. The editor
# reads at the scope it is writing, so a person is shown their own arrangement and edits it; the
# save then re-reads one scope *below* to get the list its anchors are relative to.
LAYERS_UPTO = {"base": (), "site": ("site",), "user": ("site", "user")}


def _upto(layers: dict[str, list[dict]], upto: str) -> list[list[dict]]:
	return [layers.get(role, []) for role in LAYERS_UPTO[upto]]


def _merge(base: list[dict], layers: list[list[dict]], *, keep_hidden: bool = False) -> list[dict]:
	"""Fold the layers into the base and return what the browser renders.

	The merge itself is `frappe.desk.layers`, imported rather than copied. It is 165 lines that
	do not import `frappe` at all, and it takes identity and row application as parameters, so
	desk v2 passes its own `key` and `apply_row` exactly as the dock and the sidebar each pass
	theirs.

	Hidden items are dropped here, and `keep_hidden` is the one caller that wants them: the
	arrangement editor, which has to show a person what they hid in order to let them unhide it
	(#42363). `resolve_layers` returns `(resolved, hidden)` as two values and deliberately leaves
	the flag unapplied, because the surface decides — desk v1's dock keeps a hidden entry so its
	manager can list it under Hidden, and boot drops it, since shipping a row the browser cannot
	render would spend bytes against a budget boot already manages.

	The arrangement is **anchored**: a layer moves the rows it anchored and leaves the rest of the
	list where the layer below it put it. That is what #42229's sparse move-list asked for and
	what neither half of `keep_unnamed` could give — an item an app ships later lands at its
	shipped position rather than after everything a person has arranged. #42363 settled the writer
	that produces the anchors, so the flag now has nothing left to decide and is not passed.
	"""
	resolved, hidden = resolve_layers(base, layers, key=item_key, apply_row=apply_item_row, anchored=True)

	items = resolved if keep_hidden else _drop_hidden(resolved, hidden)

	return [_on_the_wire(item, hidden) for item in _promote_orphans(items)]


def _drop_hidden(items: list[dict], hidden: dict[str, bool]) -> list[dict]:
	"""Drop every hidden item, and everything under one.

	A person hiding a section means the branch, not the header. That is the opposite of an app
	*removing* a section, where `_promote_orphans` lifts the children to the top level so an app
	never silently withdraws what was under one — and the two look identical by the time the list
	is flat, which is why the subtree has to go before orphans are promoted rather than after
	(#42363 decision 9).

	Walked upward from each row rather than downward from each section, so the cost is one pass
	over a chain per item and a section nested in a hidden section needs no second sweep. The
	`seen` set is the cycle guard: `parent_key` is authored, and a row that is its own ancestor
	would otherwise loop here rather than merely render oddly.
	"""
	parents = {item_key(item): item.get("parent_key") for item in items}
	dropped: set[str] = set()

	for key in parents:
		chain, at, seen = [], key, set()

		while at and at not in seen:
			seen.add(at)
			chain.append(at)
			if hidden.get(at) or at in dropped:
				dropped.update(chain)
				break
			at = parents.get(at)

	return [item for item in items if item_key(item) not in dropped]


def _on_the_wire(item: dict, hidden: dict[str, bool]) -> dict:
	"""One resolved item, carrying its hidden flag only when the caller kept hidden rows.

	`on_the_wire` drops every blank field, so an item that is not hidden says nothing about it
	either way — which is right for boot, where the flag cannot be false and is never read, and
	right for the editor, which asks whether the key is there.
	"""
	wire = on_the_wire(item)

	if hidden.get(item_key(item)):
		wire["hidden"] = 1

	return wire


def item_key(row) -> str | None:
	"""What identifies a navigation item: its authored, frozen `key` and nothing else.

	#42229 made the key the identity of every row an app ships, in the same sense a `fieldname`
	is: every site and user edit is filed against it, so changing one is a breaking change. That
	replaces desk v1's *computed* identity, which the client reimplemented and got wrong —
	`sidebar_manager.js:167-174` leaves `filters` out of a key the server includes.

	A row with no key names nothing. `Rail.validate_item_keys` only checks the app layer, on
	purpose, because a layer row is addressed by the base key it names; a row a *layer* added has
	its key minted when it is written, which is #42363's endpoint. Until that exists, a keyless
	row is a malformed row and `apply_item_row` drops it rather than merging every keyless row in
	a layer into one.
	"""
	return row.get("key") or None


def apply_item_row(row, entry: dict | None) -> dict | None:
	"""What one layer row does to the item it names.

	Two kinds of row, which #42229 tells apart by a stored flag rather than by inference. An
	**added** row is the item: it brings something no layer below it holds, and is rendered as it
	stands. A **delta** row states an opinion about an item already in the list, and `overrides`
	says which fields that opinion covers.

	`overrides` is an explicit list of fieldnames rather than "whatever is non-blank", and that is
	the whole point of it: a site clearing a value the app shipped — removing an icon, blanking a
	label — is not expressible in an empty-means-inherit encoding, and it also makes "did a human
	author this label" answerable at render time.

	A delta naming an item the list does not hold returns `None` and is skipped. That is #42229's
	*deltas whose base is gone are left inert*: an app can remove an item without a site's stored
	arrangement resurrecting it as an unlabelled button, and reinstalling the app restores the
	layout because the delta was never deleted.
	"""
	if not item_key(row):
		return None

	if row.get("added"):
		return {field: row.get(field) for field in ITEM_FIELDS}

	if entry is None:
		return None

	return {**entry, **{field: row.get(field) for field in _overridden(row)}}


def _overridden(row) -> list[str]:
	"""The fieldnames a delta row has an opinion about.

	Stored as JSON on the row. A row whose `overrides` will not parse is treated as having no
	opinion rather than as having an opinion about everything: the second reading would let one
	malformed row blank an item's whole presentation, which is a worse failure than a delta that
	quietly does nothing.
	"""
	try:
		overrides = json.loads(row.get("overrides") or "[]")
	except (TypeError, ValueError):
		return []

	if not isinstance(overrides, list):
		return []

	return [field for field in overrides if field in ITEM_FIELDS]


def _promote_orphans(items: list[dict]) -> list[dict]:
	"""Move an item whose parent is gone up to the top level rather than dropping it.

	`parent_key` is the whole of hierarchy, and its own description already fixes this: a
	`parent_key` naming a row that is no longer there promotes the child instead of taking it
	with it, so an app removing a section never silently removes everything under it. It also
	matches #42230's rule for a user who has reparented into a section the site later withdrew.

	It runs after `_drop_hidden`, which is what keeps the two cases apart. A person *hiding* a
	section means the whole branch, so its children are already gone by the time this runs; an app
	*removing* one does not, so its children arrive here and are lifted. The passes stopped being
	independent when #42363 gave a person a way to hide anything at all: before that, a hidden
	section and a removed one reached this line looking exactly alike.
	"""
	present = {item_key(item) for item in items}
	return [
		item if not item.get("parent_key") or item["parent_key"] in present else {**item, "parent_key": None}
		for item in items
	]


def on_the_wire(item: dict) -> dict:
	"""One resolved item as the browser gets it: the fields it renders, and only those set.

	Blank fields are omitted rather than sent as `null`. Navigation is the largest thing in a
	payload #42232 measured at 5,684 B against a 40 KB ceiling, and most fields on most rows are
	blank — a derived rail row sets four of eleven.

	`payload` is parsed here rather than sent as the string it is stored as, so the type-specific
	tail is a JSON object on both sides of the wire and no renderer parses it again. A payload
	that will not parse is dropped and logged: it is authored by whoever shipped the row, so it
	is a bug in an app rather than something a reader can act on.
	"""
	wire = {field: item.get(field) for field in WIRE_FIELDS if item.get(field)}

	if wire.get("payload"):
		wire["payload"] = _parse_payload(item)

	if item.get("switches_app"):
		wire["url"] = _switching_url(item) or wire.get("url")

	return {field: value for field, value in wire.items() if value}


def _switching_url(item: dict) -> str | None:
	"""The absolute URL of a contributed item that leaves the host, or None if it has none.

	The server builds it because the browser cannot. `routeFor` resolves through the router the
	document is standing in, so every URL it can produce is inside the current prefix — which is
	the whole reason a contributed item stays in the host by default and needs no code to do it.
	Crossing is the exception, and it is a full document load either way (#42102).

	The destination is the **contributing** app's prefix, which is what `app` on a merged item
	says. A host's own row can never reach here: nothing sets `app` on one, because nothing about
	it is foreign.

	An item whose destination has no address under that prefix falls back to the ordinary
	in-prefix link and logs — a working link in the wrong app beats no link at all. A `Module`
	under a non-modular prefix is the case: there is no module route to land on (#42211).

	A `Link` row is the one kind that is silently left alone. It already carries an absolute URL
	that goes wherever its author pointed it, so switching apps says nothing about it, and
	logging would report a mistake nobody made.
	"""
	from .doctypes import get_address_table, slug
	from .registry import declared_prefix, is_modular, shell_base

	app = item.get("app")
	if not app:
		return None

	base = shell_base(declared_prefix(app))
	modular = is_modular(app)
	item_type = item.get("item_type")

	if item_type == "Module":
		return f"{base}/{slug(item['link_to'])}" if modular and item.get("link_to") else _no_address(item)

	if item_type == "DocType":
		doctype, record = item.get("link_to"), None
	elif item_type == "Record":
		doctype, record = item.get("link_doctype"), item.get("link_to")
	elif item_type == "Link":
		return None
	else:
		return _no_address(item)

	address = get_address_table()["doctypes"].get(doctype)
	if not address:
		return _no_address(item)

	doctype_slug, module_slug = address
	if modular and not module_slug:
		return _no_address(item)

	segments = [base, module_slug, doctype_slug] if modular else [base, doctype_slug]
	if record:
		# The one request-shaped value in the path. Everything else is a slug the framework
		# computed; a record name is user data and can hold a slash.
		segments.append(quote(record, safe=""))

	return "/".join(segments)


def _no_address(item: dict) -> None:
	frappe.log_error(
		title="Navigation item cannot switch apps",
		message=(
			f"{item.get('item_type')} item {item.get('key')!r} contributed by {item.get('app')!r} "
			"has no address under that app's prefix; it stays in the host prefix."
		),
	)
	return None


def _parse_payload(item: dict) -> dict:
	try:
		payload = json.loads(item["payload"])
	except (TypeError, ValueError):
		payload = None

	if isinstance(payload, dict):
		return payload

	frappe.log_error(
		title="Navigation item has an unreadable payload",
		message=f"{item.get('item_type')} item {item.get('key')!r}: {item.get('payload')!r}",
	)
	return {}


# The stored layers
#
# Every read below is `frappe.get_all`, which does not apply permissions — and that is the point
# rather than an oversight. Both containers carry a `has_permission` hook that stops one person
# reading another's layer through the API, and `Rail`'s also withholds the app and site layers
# from a `Desk User`. Resolution is the server reading those layers *on that person's behalf* to
# build what they are allowed to see, so applying the hook here would resolve everyone's rail
# down to their own delta rows over nothing.


def _rail_layers(app: str) -> dict[str, list[dict]]:
	"""One app's three rail layers, by role, in one pair of queries.

	`standard` is absent rather than empty when the app ships no rail, because the two mean
	different things: an app that ships an empty rail has said something, and an app that ships
	none has not, and only the second derives a base.
	"""
	records = frappe.get_all(
		"Rail",
		filters={
			"app": app,
			"extends": NO_HOST,
			"user": ("in", (SITE_LAYER, frappe.session.user)),
		},
		fields=["name", "standard", "user"],
	)

	rows = _rows_by_parent("Rail", "items", [record.name for record in records])
	layers = {}

	for record in records:
		layers[_layer_role(record)] = rows.get(record.name, [])

	# `extends` is blank in the filter above, so this returns the app's own three layers and never
	# a record it ships for somebody else's rail. Those share this app's name and would otherwise
	# arrive here as a second standard layer, which the merge has no way to tell from the first.
	return layers


def _rail_contributions(host: str) -> list[tuple[str, list[dict]]]:
	"""What other apps add to this app's rail, in installation order.

	Installation order, not name order, because it is the order the site actually did things in
	and the only one an administrator can change. It decides the appended tail, and it decides
	nothing else: anchors resolve against the finished list, so an anchor naming another
	extender's item works whichever went on first (#42364).

	Active apps only — `get_active_apps` rather than the installed list, for the reason boot uses
	it: a **disabled** app must not keep serving anything, and an app still in `installed_apps`
	but gone from the bench would raise on the next hook read. An app off that list contributes
	nothing rather than contributing at the end.

	Standard rows only, which the schema already guarantees: `extends` is blanked on any row that
	is not app content, so a site or a person cannot file one app's items onto another's rail.
	"""
	records = frappe.get_all("Rail", filters={"extends": host, "standard": 1}, fields=["name", "app"])
	if not records:
		return []

	# One pass over the app list, not a scan per record: both the membership test and the sort
	# key would otherwise walk it, and this runs inside boot's blocking pre-mount fetch.
	position = {app: index for index, app in enumerate(frappe.get_active_apps(_ensure_on_bench=True))}
	records = sorted(
		(record for record in records if record.app in position), key=lambda record: position[record.app]
	)
	rows = _rows_by_parent("Rail", "items", [record.name for record in records])

	return [(record.app, _readable(rows.get(record.name, []))) for record in records]


def _readable(rows: list[dict]) -> list[dict]:
	"""Drop a contributed row pointing at a doctype this person cannot read.

	#42364's rule 6: doctype read is the only filter on a contribution, and the target app's
	`app_permission` door does **not** run — that gate is about entering a prefix, and following
	a foreign item does not leave the host.

	It is here rather than waiting for #42233, which owns filtering authored rows generally,
	because the host is the one party that cannot refuse: an app's own rows are its own problem,
	while these arrive on somebody else's rail. The narrowness is the point — this is #42231's
	`Readable DocType` bucket and only that one, read off the type table rather than hardcoded,
	so #42233 replaces it with the full dispatch rather than finding a second rule to reconcile.

	Which column names the doctype depends on the type: a `DocType` item's destination *is* the
	doctype, in `link_to`, while `Record` is the one kind that carries its own `link_doctype`.

	A dropped section leaves its children behind, and `_promote_orphans` lifts them to the top
	level on the way out — the same treatment as an app removing a section.
	"""
	if not rows:
		return rows

	from .doctypes import get_readable_doctypes

	buckets = _permission_rules()
	readable = None

	kept = []

	for row in rows:
		if buckets.get(row.get("item_type")) != READABLE_DOCTYPE:
			kept.append(row)
			continue

		if readable is None:
			# Read once, and only if a row actually asks. `get_readable_doctypes` is one
			# role-based pass measured at 25 ms against 3,594 ms for per-doctype checks, but a
			# bench where nothing extends anything should not pay even that.
			readable = get_readable_doctypes()

		doctype = row.get("link_to") if row.get("item_type") == "DocType" else row.get("link_doctype")
		if doctype in readable:
			kept.append(row)

	return kept


def _permission_rules() -> dict[str, str]:
	"""`{type: permission_rule}` — the rule each kind declares for itself (#42231)."""
	return dict(frappe.get_all("Navigation Item Type", fields=["name", "permission_rule"], as_list=True))


def _layer_role(record) -> str:
	if record.standard:
		return "standard"
	return "site" if record.user == SITE_LAYER else "user"


def _sidebar_addresses(app: str) -> list[tuple[str, str]]:
	"""The addresses of the sidebars this app ships.

	Read from the standard rows, because an app layer is what makes a sidebar exist: a site or a
	user delta over an address no app ships is inert under #42229, and a *sidebar* added by a
	layer is an addition nothing authors yet (#42363).

	`link_doctype` set is the whole test for a desk v2 row. Desk v1's sidebars carry no address
	and never will, so this one filter separates the two desks with no migration stamping rows.
	"""
	return [
		(record.link_doctype, record.link_to)
		for record in frappe.get_all(
			"Sidebar",
			filters={"app": app, "standard": 1, "link_doctype": ("is", "set")},
			fields=["link_doctype", "link_to"],
			order_by="name",
		)
		if record.link_to
	]


def _sidebar_layers(addresses: list[tuple[str, str]]) -> dict[tuple[str, str], dict[str, list[dict]]]:
	"""Every layer of every one of those addresses, in one pair of queries.

	Not one query per sidebar: a modular app has one sidebar per module, so per-address reads
	would put two queries per module into the blocking pre-mount path (#42070).
	"""
	doctypes = {address[0] for address in addresses}
	records = frappe.get_all(
		"Sidebar",
		filters={
			"link_doctype": ("in", doctypes),
			"user": ("in", (SITE_LAYER, frappe.session.user)),
		},
		fields=["name", "standard", "user", "link_doctype", "link_to"],
	)
	# The query filters on `link_doctype` alone, since a tuple is not a filter; the pair is
	# checked here. A row at an address this app does not ship is another app's, or a delta over
	# an address nobody ships, and neither belongs in this payload.
	wanted = set(addresses)
	records = [record for record in records if (record.link_doctype, record.link_to) in wanted]

	# `navigation_items`, never `items`. One `Sidebar` document holds both tables — desk v1's
	# rows and desk v2's — so naming the parentfield is what keeps a v2 resolver from silently
	# rendering v1's sidebar.
	rows = _rows_by_parent("Sidebar", "navigation_items", [record.name for record in records])
	layers: dict[tuple[str, str], dict[str, list[dict]]] = {}

	for record in records:
		address = (record.link_doctype, record.link_to)
		layers.setdefault(address, {})[_layer_role(record)] = rows.get(record.name, [])

	return layers


def _rows_by_parent(parenttype: str, parentfield: str, parents: list[str]) -> dict[str, list[dict]]:
	if not parents:
		return {}

	rows: dict[str, list[dict]] = {}

	for row in frappe.get_all(
		"Navigation Item",
		filters={"parent": ("in", parents), "parenttype": parenttype, "parentfield": parentfield},
		fields=["parent", *ITEM_FIELDS],
		order_by="parent asc, idx asc",
	):
		rows.setdefault(row.pop("parent"), []).append(row)

	return rows


# Deriving a rail for an app that ships none


def _derive_rail(app: str) -> list[dict]:
	"""An app's rail when it ships no `Rail` record: its own doctypes, permission-filtered.

	This is what `frappe.shell.doctypes` has been serving the rail all along, in the item shape
	the rest of this module speaks. It is the honest default for an app that has no opinions yet,
	and it is what keeps five apps' rails from going blank on the day the resolver lands.

	The key is the doctype name. Derived items need a stable one to file deltas against, and the
	doctype name is already what the address table is keyed on, so it stays stable through a slug
	change and through the app's eventual conversion to shipped rows.

	No label and no icon, because nobody authored either. A renderer falls back to the destination
	for a row that carries no label, which is what the rail shows today — so the appearance
	changes when an app ships rows, not when this lands.
	"""
	from .doctypes import get_address_table, get_doctype_owners, get_readable_doctypes

	addressable = get_address_table()["doctypes"]
	readable = get_readable_doctypes()
	owners = get_doctype_owners()

	return [
		{"key": doctype, "item_type": "DocType", "link_doctype": "DocType", "link_to": doctype}
		for doctype in sorted(owners)
		if owners[doctype] == app and doctype in addressable and doctype in readable
	]
