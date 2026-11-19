# NAVIGATION — the rail and the sidebars of one prefix, resolved for one user.

# One entry point, and nothing here is whitelisted: `get_boot` has already checked the prefix
# registry and `has_app_permission`, so a second trust boundary here would duplicate it.

import json
from typing import NamedTuple
from urllib.parse import quote

import frappe
from frappe.desk.doctype.navigation_item.nesting import cap_depth
from frappe.desk.layers import resolve_layers

from .extensions import extend
from .navigation_filter import NavigationContext, filter_items

# What a stored row carries. Read as columns, not a document: `Sidebar`'s class is desk v1's
# and its record holds v1's `items` beside v2's `navigation_items`.
ITEM_FIELDS = (
	"key",
	"parent_key",
	"item_type",
	"link_doctype",
	"link_to",
	"opens_sidebar",
	"url",
	"payload",
	"label",
	"icon",
	"collapsible",
	"keep_closed",
	"hidden",
	"added",
	"overrides",
	# Read for the extension merge, not the browser: `overrides` may name either.
	"anchors",
	"switches_app",
)

# What reaches the browser. `hidden`, `added` and `overrides` are how a layer was stored.
WIRE_FIELDS = (
	"key",
	"parent_key",
	"item_type",
	"link_doctype",
	"link_to",
	"opens_sidebar",
	"url",
	"payload",
	"label",
	"icon",
	"collapsible",
	"keep_closed",
)

# `Rail.SITE_LAYER` and `Sidebar.SITE_LAYER`: one spelling has to reach the unique index.
SITE_LAYER = ""

# `Rail.NO_HOST`: an app's own rail extends nobody, and the layer query below filters on it.
NO_HOST = ""

# `Rail.navigation_layout`, and the levels it resolves through, person first.
NAVIGATION_LAYOUTS = ("rail_and_sidebar", "sidebar_only", "floating_rail")
DEFAULT_LAYOUT = "rail_and_sidebar"
LAYOUT_LEVELS = ("user", "site", "standard")


def resolve_navigation(app: str) -> dict:
	"""`{"rail", "sidebars", "navigation_layout"}` for one prefix, as the session user sees it."""
	# Sidebars are keyed by scrubbed address, which is what a rail item of type `Sidebar` carries
	# in `link_to`; no one record's name identifies a sidebar merged from three rows.

	# The sidebars resolve first: a rail item of type `Sidebar` survives only while its sidebar
	# holds a row. One context, so each permission set is read once.
	context = NavigationContext(app)
	sidebars = context.sidebars

	layers = _rail_layers(app)
	navigation = {
		"rail": _without_missing_sidebars(resolve_rail(app, context=context, layers=layers), sidebars),
		# A sidebar row opens nothing beside its target.
		"sidebars": {key: _without_missing_sidebars(rows, {}) for key, rows in sidebars.items()},
		"navigation_layout": resolve_navigation_layout(layers.layouts),
	}

	# Sent only when true: a person who pinned a floating rail is the rare case, and the boot is
	# byte-budgeted.
	if _is_pinned(layers.layouts):
		navigation["pinned"] = True

	# Likewise: a pin writes the person's own `rail_and_sidebar`, and only a floating rail below
	# makes the unpin button show, so a floating rail over another layout offers no pin.
	if _can_pin(layers.layouts):
		navigation["can_pin"] = True

	return navigation


def _without_missing_sidebars(rail: list[dict], sidebars: dict[str, list[dict]]) -> list[dict]:
	"""The rail with `opens_sidebar` dropped where its sidebar is not here, so the row opens its own target."""
	# No visible rows, or not this person's: the row then draws as independent.
	return [
		{field: value for field, value in row.items() if field != "opens_sidebar"}
		if row.get("opens_sidebar") and row["opens_sidebar"] not in sidebars
		else row
		for row in rail
	]


def resolve_rail(
	app: str,
	*,
	upto: str = "user",
	keep_hidden: bool = False,
	check_permission: bool = True,
	context: NavigationContext | None = None,
	layers: "RailLayers | None" = None,
) -> list[dict]:
	"""One app's rail: its own layer plus what other apps add to it, then the site's, then this user's."""
	# `upto` and `keep_hidden` are the arrangement editor's, and `check_permission=False` is its
	# site-scope bypass, the only one in the system.

	# Extension happens to the base, before the site and user layers, so a person's arrangement
	# of a host rail is one row. A derived base takes the same merge, so the overlay works on it.
	rows = dict((layers or _rail_layers(app)).rows)
	base = rows.pop("standard", None)
	# A derived base's keys are doctype names nobody authored, so an anchor may not name one.
	shipped = base is not None
	if base is None:
		base = _derive_rail(app)

	base = extend(base, _rail_contributions(app), anchorable=shipped)

	return _merge(
		"Rail",
		base,
		_upto(rows, upto),
		keep_hidden=keep_hidden,
		context=_context(app, context, check_permission),
	)


def resolve_navigation_layout(by_role: dict[str, str]) -> str:
	"""The first value set at person, then site, then app; `rail_and_sidebar` when none is."""
	return layout_below(by_role, None)


def layout_below(by_role: dict[str, str], role: str | None) -> str:
	"""What a layer's blank resolves to: the levels under `role` (all of them when it is `None`)."""
	levels = LAYOUT_LEVELS[LAYOUT_LEVELS.index(role) + 1 :] if role else LAYOUT_LEVELS
	return next((by_role[level] for level in levels if by_role.get(level)), DEFAULT_LAYOUT)


def rail_layouts(app: str) -> dict[str, str]:
	"""The navigation layout each level of this app's rail sets; a level with no record is absent."""
	return _rail_layers(app).layouts


def _is_pinned(by_role: dict[str, str]) -> bool:
	"""The person's own `rail_and_sidebar` sits over an inherited floating rail, which is what a pin writes."""
	return by_role.get("user") == DEFAULT_LAYOUT and layout_below(by_role, "user") == "floating_rail"


def _can_pin(by_role: dict[str, str]) -> bool:
	"""The floating rail is drawn and the level below the person's is a floating rail: a pin can be undone."""
	return (
		resolve_navigation_layout(by_role) == "floating_rail"
		and layout_below(by_role, "user") == "floating_rail"
	)


def resolve_sidebars(app: str, context: NavigationContext | None = None) -> dict[str, list[dict]]:
	"""Every sidebar this app ships and every own sidebar of this level and the person's, resolved."""
	# A shipped sidebar is keyed by its scrubbed address and an own sidebar by its `key`; a scrub holds no `:`.
	# Empty until an app ships rows: derivation produces a rail and nothing else.
	addresses = _sidebar_addresses(app)
	if not addresses:
		return {}

	# Always filtered: boot is the only caller that wants a whole prefix, and boot never bypasses.
	context = context or NavigationContext(app)
	layers = _sidebar_layers(addresses)
	resolved = {}

	for address in addresses:
		# Before the rows and the layers: a blocked module ships nothing and no layer may put it back.
		if not context.address_is_offered(*address):
			continue

		by_layer = layers.get(address, {})
		base = by_layer.get("standard", [])
		items = _merge("Sidebar", base, _upto(by_layer, "user"), context=context)
		if items:
			# Absent, not empty: the payload is read by key, and the rail item for this address
			# goes with it.
			resolved[_boot_key(address)] = items

	return resolved


def resolve_sidebar(
	link_doctype: str,
	link_to: str,
	*,
	upto: str = "user",
	keep_hidden: bool = False,
	check_permission: bool = True,
	layers: dict[str, list[dict]] | None = None,
) -> list[dict]:
	"""One sidebar at one address, for a caller that wants that one and not the prefix.

	`layers` is this address's layers by role, for a caller that loaded many addresses in one go.
	"""
	# No app to build a context for: the one rule that reaches across containers runs on the rail.
	context = NavigationContext("") if check_permission else None

	if context is not None and not context.address_is_offered(link_doctype, link_to):
		return []

	by_layer = (
		layers
		if layers is not None
		else _sidebar_layers([(link_doctype, link_to)]).get((link_doctype, link_to), {})
	)

	return _merge(
		"Sidebar",
		by_layer.get("standard", []),
		_upto(by_layer, upto),
		keep_hidden=keep_hidden,
		context=context,
	)


# The layers a resolution stacks, in order, up to and including the scope asked for.
LAYERS_UPTO = {"base": (), "site": ("site",), "user": ("site", "user")}


def _upto(layers: dict[str, list[dict]], upto: str) -> list[list[dict]]:
	return [layers.get(role, []) for role in LAYERS_UPTO[upto]]


def _context(app: str, context: "NavigationContext | None", check_permission: bool):
	"""The context a resolution filters against, or `None` for the editor's bypass."""
	if not check_permission:
		return None

	return context or NavigationContext(app)


def _merge(
	container: str,
	base: list[dict],
	layers: list[list[dict]],
	*,
	keep_hidden: bool = False,
	context: "NavigationContext | None" = None,
) -> list[dict]:
	"""Fold the layers into the base and return what the browser renders."""
	# `resolve_layers` leaves the hidden flag unapplied because the surface decides; the
	# arrangement editor is the one caller that keeps hidden rows.

	# Anchored: a layer moves the rows it anchored and leaves the rest where the layer below put them.
	resolved, hidden = resolve_layers(base, layers, key=item_key, apply_row=apply_item_row, anchored=True)

	items = resolved if keep_hidden else _drop_hidden(resolved, hidden)

	# Filtering after the arrangement, so a stored move means the same for two people, and after
	# `_drop_hidden`, so a hidden subtree never counts as a section's children.
	if context is not None:
		items = filter_items(items, context)

	# After `_promote_orphans`: a lifted row's new parent must still be there.
	return [_on_the_wire(item, hidden) for item in cap_depth(_promote_orphans(items), container)]


def _drop_hidden(items: list[dict], hidden: dict[str, bool]) -> list[dict]:
	"""Drop every hidden item, and everything under one."""
	# Before `_promote_orphans`: hiding a section means the branch, removing one means the header,
	# and the two look identical once the list is flat.

	# `seen` is the cycle guard: `parent_key` is authored, and a row can be its own ancestor.
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
	"""One resolved item, carrying its hidden flag only when the caller kept hidden rows."""
	wire = on_the_wire(item)

	if hidden.get(item_key(item)):
		wire["hidden"] = 1

	return wire


def item_key(row) -> str | None:
	"""What identifies a navigation item: its authored, frozen `key` and nothing else."""
	# A keyless row names nothing and is dropped, or every keyless row in a layer would merge into one.
	return row.get("key") or None


def apply_item_row(row, entry: dict | None) -> dict | None:
	"""What one layer row does to the item it names: an added row is the item, a delta overrides it."""
	# `overrides` is an explicit fieldname list, so a site can blank a value the app shipped.
	# A delta naming an item the list does not hold is inert, so a removed item is not resurrected.
	if not item_key(row):
		return None

	if row.get("added"):
		return {field: row.get(field) for field in ITEM_FIELDS}

	if entry is None:
		return None

	return {**entry, **{field: row.get(field) for field in _overridden(row)}}


def _overridden(row) -> list[str]:
	"""The fieldnames a delta row has an opinion about; one that will not parse has none."""
	try:
		overrides = json.loads(row.get("overrides") or "[]")
	except (TypeError, ValueError):
		return []

	if not isinstance(overrides, list):
		return []

	return [field for field in overrides if field in ITEM_FIELDS]


def _promote_orphans(items: list[dict]) -> list[dict]:
	"""Lift an item whose parent is gone to the top level instead of dropping it."""
	# After `_drop_hidden`: a hidden section takes its branch, a removed one leaves its children.
	present = {item_key(item) for item in items}
	return [
		item if not item.get("parent_key") or item["parent_key"] in present else {**item, "parent_key": None}
		for item in items
	]


def on_the_wire(item: dict) -> dict:
	"""One resolved item as the browser gets it: the fields it renders, and only those set."""
	# Blank fields are omitted: navigation is most of the boot budget and most fields are blank.
	# `payload` is parsed here so no renderer parses it again; an unparsable one is logged.
	wire = {field: item.get(field) for field in WIRE_FIELDS if item.get(field)}

	if wire.get("payload"):
		wire["payload"] = _parse_payload(item)

	if item.get("switches_app"):
		wire["url"] = _switching_url(item) or wire.get("url")

	return {field: value for field, value in wire.items() if value}


def _switching_url(item: dict) -> str | None:
	"""The absolute URL of a contributed item that leaves the host, or None if it has none."""
	# Built here because `routeFor` in the browser resolves inside the current prefix. A destination
	# with no address under the contributing prefix falls back to the in-prefix link and logs.
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
	# A `Link` already carries an absolute URL; switching apps says nothing about it.
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
		# A record name is user data and can hold a slash.
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

# Every read below is `frappe.get_all`, which applies no permissions, on purpose: resolution
# reads the layers on the person's behalf, and the containers' `has_permission` hooks guard the API.


class RailLayers(NamedTuple):
	"""One app's rail layers by role: the rows each holds, and the navigation layout it sets."""

	rows: dict[str, list[dict]]
	layouts: dict[str, str]


def _rail_layers(app: str) -> RailLayers:
	"""One app's three rail layers, by role, in one pair of queries."""
	# `standard` is absent, not empty, when the app ships no rail; only absent derives a base.
	records = frappe.get_all(
		"Rail",
		filters={
			"app": app,
			"extends": NO_HOST,
			"user": ("in", (SITE_LAYER, frappe.session.user)),
		},
		fields=["name", "standard", "user", "navigation_layout"],
	)

	rows = _rows_by_parent("Rail", "items", [record.name for record in records])
	layers = RailLayers({}, {})

	for record in records:
		role = _layer_role(record)
		layers.rows[role] = rows.get(record.name, [])
		layers.layouts[role] = record.navigation_layout or ""

	# `extends` is blank in the filter, so a record this app ships for another app's rail never
	# arrives as a second standard layer.
	return layers


def _rail_contributions(host: str) -> list[tuple[str, list[dict]]]:
	"""What other apps add to this app's rail, in installation order, unfiltered."""
	# Active apps only, as boot: a disabled app contributes nothing, and one gone from the bench
	# would raise on the next hook read.

	# Unfiltered here: contributed rows take the same pass as everything else, on their own bucket.
	records = frappe.get_all("Rail", filters={"extends": host, "standard": 1}, fields=["name", "app"])
	if not records:
		return []

	# One pass over the app list, not a scan per record; this is inside boot's blocking fetch.
	position = {app: index for index, app in enumerate(frappe.get_active_apps(_ensure_on_bench=True))}
	records = sorted(
		(record for record in records if record.app in position), key=lambda record: position[record.app]
	)
	rows = _rows_by_parent("Rail", "items", [record.name for record in records])

	return [(record.app, rows.get(record.name, [])) for record in records]


def _layer_role(record) -> str:
	if record.standard:
		return "standard"
	return "site" if record.user == SITE_LAYER else "user"


def _sidebar_addresses(app: str) -> list[tuple[str, str]]:
	"""The addresses of the sidebars this app ships, then the own sidebars of the site and this person."""
	# `link_doctype` set is the whole test for a shipped desk v2 row; v1's sidebars carry no address.
	# An own sidebar's address is `("", key)`.
	shipped = [
		(record.link_doctype, record.link_to)
		for record in frappe.get_all(
			"Sidebar",
			filters={"app": app, "standard": 1, "link_doctype": ("is", "set")},
			fields=["link_doctype", "link_to"],
			order_by="name",
		)
		if record.link_to
	]

	return shipped + [("", key) for key in _own_sidebar_keys(app)]


def _own_sidebar_keys(app: str) -> list[str]:
	"""The keys this app's own sidebars carry at the site layer and this person's."""
	# A person's record at a `site:` key arranges the site's sidebar; it is no sidebar when the site's is gone.
	records = frappe.get_all(
		"Sidebar",
		filters={
			"app": app,
			"standard": 0,
			"key": ("is", "set"),
			"user": ("in", (SITE_LAYER, frappe.session.user)),
		},
		fields=["key", "user"],
		order_by="key",
	)

	return [record.key for record in records if record.user == SITE_LAYER or record.key.startswith("user:")]


def _sidebar_layers(addresses: list[tuple[str, str]]) -> dict[tuple[str, str], dict[str, list[dict]]]:
	"""Every layer of every one of those addresses, in one pair of queries, not one per sidebar."""
	doctypes = {address[0] for address in addresses if address[0]}
	keys = {address[1] for address in addresses if not address[0]}
	records = frappe.get_all(
		"Sidebar",
		filters={"user": ("in", (SITE_LAYER, frappe.session.user))},
		or_filters=[
			*([["link_doctype", "in", list(doctypes)]] if doctypes else []),
			*([["key", "in", list(keys)]] if keys else []),
		],
		fields=["name", "standard", "user", "link_doctype", "link_to", "key"],
	)
	# A tuple is not a filter, so the pair is checked here; a row at an address this app does
	# not ship is another app's, or a delta over nothing.
	wanted = set(addresses)
	records = [record for record in records if _record_address(record) in wanted]

	# `navigation_items`, never `items`: one `Sidebar` document holds v1's table beside v2's.
	rows = _rows_by_parent("Sidebar", "navigation_items", [record.name for record in records])
	layers: dict[tuple[str, str], dict[str, list[dict]]] = {}

	for record in records:
		layers.setdefault(_record_address(record), {})[_layer_role(record)] = rows.get(record.name, [])

	return layers


def _record_address(record) -> tuple[str, str]:
	return (record.link_doctype, record.link_to) if record.link_doctype else ("", record.key)


def _boot_key(address: tuple[str, str]) -> str:
	"""What `navigation.sidebars` files a sidebar under: the key of an own one, else the scrubbed address."""
	return frappe.scrub(f"{address[0]} {address[1]}") if address[0] else address[1]


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
	"""An app's rail when it ships no `Rail` record: its own doctypes, permission-filtered."""
	# The key is the doctype name, which stays stable through a slug change and a later conversion.
	# No label and no icon, because nobody authored either; the renderer falls back to the destination.
	from .doctypes import get_readable_doctypes, get_shell_doctypes

	doctypes = get_shell_doctypes()
	addressable = doctypes["table"]["doctypes"]
	readable = get_readable_doctypes()
	owners = doctypes["owners"]

	return [
		{"key": doctype, "item_type": "DocType", "link_doctype": "DocType", "link_to": doctype}
		for doctype in sorted(owners)
		if owners[doctype] == app and doctype in addressable and doctype in readable
	]


def report_overlaps(app: str) -> dict:
	"""Destinations this app offers from more than one panel, as the session user sees it; run by hand."""
	navigation = resolve_navigation(app)
	sidebars = navigation["sidebars"]

	# Cold-load order is the rail top to bottom. A panel no rail item opens sorts last.
	rail_order = {
		item.get("link_to"): index
		for index, item in enumerate(navigation["rail"])
		if item.get("item_type") == "Sidebar" and item.get("link_to")
	}

	shared: dict[tuple, list[tuple[str, str]]] = {}
	repeated = []

	for address, rows in sorted(sidebars.items()):
		seen: dict[tuple, str] = {}
		for row in rows:
			destination = _destination_of(row)
			if not destination:
				continue

			if destination in seen:
				repeated.append(
					{
						"panel": address,
						"destination": " ".join(destination),
						"kept": seen[destination],
						"shadowed": row.get("key"),
					}
				)
			else:
				seen[destination] = row.get("key")
				shared.setdefault(destination, []).append((address, row.get("key")))

	return {
		"shared": [
			{
				"destination": " ".join(destination),
				"panels": [address for address, _ in places],
				"cold_load": min(
					(address for address, _ in places),
					key=lambda address: rail_order.get(address, len(rail_order)),
				),
			}
			for destination, places in sorted(shared.items())
			if len(places) > 1
		],
		"repeated": repeated,
	}


def _destination_of(item: dict) -> tuple | None:
	"""What an item points at, or None for a row that goes nowhere.

	The `(link_doctype, link_to)` pair is the address, so kind and label do not distinguish two
	rows aimed at one place.
	"""
	if item.get("item_type") in ("Link", "Section") or not item.get("link_to"):
		return None

	return (item.get("link_doctype") or item.get("item_type"), item.get("link_to"))
