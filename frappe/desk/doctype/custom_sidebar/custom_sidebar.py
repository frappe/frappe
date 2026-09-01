# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.desk.doctype.sidebar.sidebar import (
	LINKED_IDENTITY_FIELDS,
	is_linked,
	item_key,
)
from frappe.desk.doctype.workspace.workspace import check_workspace_manager, is_workspace_manager
from frappe.desk.layers import resolve_layers
from frappe.model.document import Document

SITE_LAYER = ""

# What a row carries when it is an item rather than a reference to one. These are the same fields
# a base item has, because an added item renders through the same code, with one exception:
# `is_default_module`. Only apps claim ownership; sites do not.
#
# Ownership is an app-authored fact about a product, not a site preference, and this layer is
# one-way: a site could add a flagged row to claim an entity, but no reference field could ever
# un-claim one an app shipped, since `REFERENCE_FIELDS` is only `label` and `icon`. Leaving it in
# would offer half a mechanism. A site that disagrees about where an entity lives edits the
# sidebar so the entity is a member of the one it wants, because membership is what routes you.
ADDED_ITEM_FIELDS = (
	"type",
	"label",
	"link_type",
	"link_to",
	"icon",
	"child",
	"indent",
	"collapsible",
	"keep_closed",
	"url",
	"show_arrow",
	"filters",
	"route_options",
	"open_in_new_tab",
)

# What a reference row may override on the base item it names. The list is short on purpose: a
# reference stores an override, never a copy. Storing the whole body would let one reorder freeze
# the site's labels and the app's links forever.
REFERENCE_FIELDS = ("label", "icon")

# Membership is not in that list and is not an override: it is arrangement, like order and
# `hidden`. Every row a layer holds states it, because a `Check` cannot express "no opinion"
# separately from "not a member". It does not need to, since a save writes the whole arrangement
# and the editor is given the membership it is arranging.
#
# That is safe because of where the value comes from: the editor re-reads it only for the row the
# user dragged, so every other row hands back what it was shown.


class CustomSidebar(Document):
	_DOCTYPE_NAME = "Custom Sidebar"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.sidebar_item.sidebar_item import SidebarItem
		from frappe.types import DF

		header_icon: DF.Icon | None
		label: DF.Data | None
		module: DF.Link
		sidebar_items: DF.Table[SidebarItem]
		user: DF.Link | None
	# end: auto-generated types

	def validate(self):
		self.validate_module()
		self.validate_unique()
		self.drop_private_workspaces()
		self.anchor_the_items()

	def validate_module(self):
		"""Check the module in the model rather than in the endpoints. `_validate_links` below no
		longer checks this document's own Link fields, so nothing else would."""
		check_module(self.module)

	def validate_unique(self):
		existing = frappe.db.exists(
			self._DOCTYPE_NAME,
			{
				"module": self.module,
				"user": self.user or SITE_LAYER,
				"name": ["!=", self.name],
			},
		)
		if existing:
			frappe.throw(
				_("A customization for {0} already exists for this layer.").format(self.module),
				frappe.DuplicateEntryError,
			)

	def drop_private_workspaces(self):
		"""Drop rows naming a private workspace from any layer, the site's and a user's alike.

		A private page's link is derived on read (`sidebar.get_private_workspaces`), and the
		derived row is appended to the arrangement the client is shown, so it comes back on the
		next save. Storing it would put a row per private page in the document the whole site
		shares, or, in the owner's own layer, a second copy of a link that is already derived
		from the workspace and that points nowhere once the page is deleted.

		This is enforced here rather than in the endpoints, because every write is a way in: the
		two save endpoints, `add_site_sidebar_item`, the form and the API. It also clears rows a
		site stored before the derivation existed, on the next save of that layer.

		A public workspace is untouched: its link is stored, and arranging or hiding it is what
		the layers are for.
		"""
		named = {row.link_to for row in self.sidebar_items if row.link_type == "Workspace" and row.link_to}
		if not named:
			return

		private = set(
			frappe.get_all("Workspace", filters={"name": ["in", list(named)], "public": 0}, pluck="name")
		)
		if private:
			self.set(
				"sidebar_items",
				[
					row
					for row in self.sidebar_items
					if not (row.link_type == "Workspace" and row.link_to in private)
				],
			)

	def anchor_the_items(self):
		"""Require every row to name a base item the way the model names one.

		A reference that names nothing, with no link and no key, is dropped rather than given a
		derived identity. A derived identity would be a coincidence, and coinciding with a real
		base item is worse than naming nothing. An added row is an item and names itself, from the
		same columns a base item is named by. Nothing is anchored to a row's `name`, because child
		rows are hash-named and recreated on every save.

		A linked row's stored key is blanked here. Its columns are its identity, and a rename
		rewrites them for base and delta together, so a key stored beside them would survive the
		rename still naming the old target.
		"""
		self.set(
			"sidebar_items",
			[row for row in self.sidebar_items if row.added or is_linked(row) or row.key],
		)
		for row in self.sidebar_items:
			if is_linked(row):
				row.key = None

	def _validate_links(self):
		"""Skip link validation, because a row names a document rather than referencing it.

		Frappe checks that a Dynamic Link's target still exists on every save. Here that would
		mean one deleted report turning every later write to this layer into an error, whether
		relabelling the sidebar or adding a new workspace's link. A row naming something that is
		gone stops applying when the sidebar resolves, which is what an app deleting an item has
		always done to a delta naming it.

		`ignore_links_on_delete` in hooks is the same decision from the other side of the link: a
		sidebar preference must not stop a document being deleted.
		"""
		return

	def on_update(self):
		self.clear_customization_cache()

	def on_trash(self):
		self.clear_customization_cache()

	def clear_customization_cache(self):
		if self.user:
			# A user-scoped arrangement only invalidates that user's boot.
			frappe.cache.hdel("bootinfo", self.user)
		else:
			frappe.cache.delete_key("bootinfo")


def get_layers_for(user: str, modules: list[str] | None = None) -> dict[str, list["CustomSidebar"]]:
	"""Return every layer that applies to `user`, keyed by module and in application order.

	Which layers apply depends on the user, not the module: the site's layer and the user's own.
	So it is answered once for however many modules are being resolved, the same batching
	`SidebarContext` does for the bases, the workspaces and the onboardings.

	It is one indexed query. It replaces a site-wide redis set of every `(module, user)` pair,
	read in full on every boot to gate a per-module `db.exists`. That set was keyed by the wrong
	thing: it grew with users times modules, so a site with five thousand users who had each
	arranged three modules deserialized fifteen thousand pairs to answer about one, and it needed
	invalidating. The cost of a user's own layers is now proportional to how much that user has
	customized.
	"""
	filters = {"user": ["in", [SITE_LAYER, user]]}
	if modules is not None:
		filters["module"] = ["in", modules]

	rows = frappe.get_all("Custom Sidebar", filters=filters, fields=["name", "module", "user"])
	# The site's layer first, then the user's own. Sorted here rather than relying on the
	# column's sort order, since a blank `user` collating before an email address is a database
	# detail, not the application order.
	rows.sort(key=lambda row: bool(row.user))

	layers: dict[str, list[CustomSidebar]] = {}
	for row in rows:
		layers.setdefault(row.module, []).append(frappe.get_cached_doc("Custom Sidebar", row.name))

	return layers


def get_customization(module: str, user: str | None) -> "CustomSidebar | None":
	"""Return the customization for one module and one layer, or None.

	This is what the write paths need. A resolution covering many modules calls `get_layers_for`
	once instead of calling this per module.
	"""
	name = frappe.db.exists("Custom Sidebar", {"module": module, "user": user or ["in", ["", None]]})
	return frappe.get_cached_doc("Custom Sidebar", name) if name else None


def get_layers(module: str, user: str | None) -> list["CustomSidebar"]:
	"""Return the layers to apply to `module`, in order: the site's first, then the user's own.

	Later layers win, so a user's `hidden: 0` un-hides something the site hid, which is what a
	per-user layer is for.

	A `user` of `None` means the site's layer alone. It used to mean the site's layer twice, since
	`get_customization(module, None)` and `get_customization(module, user)` both resolve to it.
	The merge is idempotent so that worked, but it was not what any caller asked for.
	"""
	layers = [get_customization(module, None)]
	if user:
		layers.append(get_customization(module, user))

	return [layer for layer in layers if layer]


def check_module(module: str) -> None:
	"""Throw unless `module` exists, since a layer is anchored to a module.

	It checks the module, not its sidebar. Most modules have no `Sidebar` document, because their
	base is computed from their contents, and those are customizable, readable and resettable on
	the same terms as a shipped one. What must exist is what the layer is anchored to.
	"""
	if not frappe.db.exists("Module Def", module):
		frappe.throw(_("{0} is not a module.").format(module))


# ---------------------------------------------------------------------------------------
# The merge engine
# ---------------------------------------------------------------------------------------


def resolve_arrangement(
	items: list[dict], layers: list["CustomSidebar"]
) -> tuple[list[dict], dict[str, bool]]:
	"""Fold each layer into `items` in order, returning the result and which items are hidden.

	The merge is `frappe.desk.layers`, which the dock also uses. The sidebar supplies the two
	pieces passed in here: how an item is identified (`item_key`) and what a row does to the item
	it names (`apply_sidebar_row`).

	What to do with a hidden item is left to the caller, because the sidebar's two callers differ:
	rendering drops it (`merge_layers`), and the editor keeps it (`layer_arrangement`), since an
	editor that cannot see a hidden item cannot offer to bring it back.
	"""
	return resolve_layers(
		items,
		[layer.sidebar_items for layer in layers],
		key=item_key,
		apply_row=apply_sidebar_row,
	)


def merge_layers(items: list[dict], layers: list["CustomSidebar"]) -> list[dict]:
	"""Return the arrangement as it renders. An item left hidden by every layer is removed, rather
	than rendered as hidden the way the dock renders one."""
	resolved, hidden = resolve_arrangement(items, layers)

	kept = []
	for item in resolved:
		if hidden.get(item_key(item)):
			continue

		# The base's own flag has already done its work, in the seed `resolve_arrangement`
		# builds. Leaving it behind would put `hidden` on an item the payload is about to
		# render, which happens whenever a layer above brings back something the app ships off
		# by default. Popping is safe because every item here is a dict the merge just built.
		item.pop("hidden", None)
		kept.append(item)

	return kept


def apply_sidebar_row(row, item: dict | None) -> dict | None:
	"""Apply one customization row to the base item it names.

	An `added` row is an item, so it replaces whatever the list holds under that key, which is
	usually nothing. A reference row overrides fields on an item that is already there, and
	`overrides` keeps that to the fields it sets: a reference stores overrides, never a copy.

	A reference naming an item the list does not hold returns `None` and is skipped rather than
	raising. That makes an app re-authoring its sidebar non-fatal: some rows survive, the rest
	stop applying. It is also the answer for a row naming an item this user may not see, since the
	layers are applied after permission filtering.
	"""
	if row.added:
		return shape_added_item(row)

	if item is None:
		return None

	return {**item, **overrides(row), "child": int(row.child or 0)}


def overrides(row) -> dict:
	"""Return what a reference row overrides on the item it names. An empty field overrides
	nothing.

	Membership is not included (see `REFERENCE_FIELDS`), because every row states it outright and
	a blank value means "not a member" rather than "ask the layer below".
	"""
	return {field: row.get(field) for field in REFERENCE_FIELDS if row.get(field)}


def shape_added_item(row) -> dict:
	"""Return an added row in the shape the boot payload uses for a base item."""
	item = {field: row.get(field) for field in ADDED_ITEM_FIELDS}
	item.update(
		{
			"key": item_key(row),
			"label": _(row.label),
			"tab": row.navigate_to_tab,
			"added": 1,
		}
	)
	return item


# ---------------------------------------------------------------------------------------
# Read API: what the editor opens on
#
# One endpoint per layer, each with its own gate, the same as the dock's reads and this module's
# saves and resets. A single endpoint taking a layer name would put the gate in a branch instead.
# ---------------------------------------------------------------------------------------


def layer_arrangement(module: str, user: str | None) -> list[dict]:
	"""Return `module`'s sidebar as one layer arranges it, keeping hidden items.

	This is what the editor opens on, and it differs from the two answers that already exist. The
	boot payload is the resolution for the user and drops hidden items, and an editor that cannot
	see a hidden item cannot offer to bring it back. A layer's stored rows are a delta, and this
	editor saves the whole arrangement.

	The layer being edited is included, so the result is the arrangement as it stands. An
	unarranged layer therefore reads as the layer below it, as that layer renders. That rule is
	applied here rather than seeded in the client, because a save writes the whole arrangement and
	starting from anything else would silently un-hide what a lower layer hid.

	`added` marks only this layer's own added rows. An item added by a lower layer is a reference
	from here; marking it as added would copy its body into this layer and freeze the label, icon
	and link the lower layer owns, which is what `REFERENCE_FIELDS` exists to prevent.

	The two layers differ on the permission filter, the same as the dock's two reads. A user's own
	arrangement is what is in front of them, so it is filtered. The site's is not: permission is a
	fact about each user, applied to what they boot, so it is not part of what the site arranged.
	A curator given a filtered screen would drop the site's rows for everything they personally
	cannot see on the next save, since this editor writes the whole arrangement.

	Private workspaces are absent, as they are from every stored arrangement: they are derived
	after the merge, and `drop_private_workspaces` removes any that were stored.
	"""
	from frappe.desk.doctype.sidebar.sidebar import filter_sidebar_items, get_module_base

	check_module(module)

	base = get_module_base(module)
	# `is_item_allowed` is a method on `DeskViews`, so the check needs an instance: one throwaway
	# `Workspace`, the same as `SidebarContext` builds for the boot.
	items = filter_sidebar_items(base.rows, frappe.new_doc("Workspace"), check_permission=bool(user))
	resolved, hidden = resolve_arrangement(items, get_layers(module, user))

	own = get_customization(module, user)
	own_added = {item_key(row) for row in own.sidebar_items if row.added} if own else set()

	return [
		{
			**item,
			"hidden": int(hidden.get(item_key(item), 0)),
			"added": int(item_key(item) in own_added),
		}
		for item in resolved
	]


@frappe.whitelist()
def get_user_sidebar_layer(module: str) -> list[dict]:
	"""Return how this user has `module`'s sidebar arranged. No gate, because it is theirs."""
	return layer_arrangement(module, frappe.session.user)


@frappe.whitelist()
def get_site_sidebar_layer(module: str) -> list[dict]:
	check_workspace_manager(_("You need to be Workspace Manager to see the sidebar's site layer."))
	return layer_arrangement(module, None)


# ---------------------------------------------------------------------------------------
# Write API
# ---------------------------------------------------------------------------------------


def module_payload(**extra) -> dict:
	"""Return the desk state a customization write invalidates, for the client to swap in."""
	from frappe.boot import build_entity_module_map, get_module_sidebars

	module_sidebars = get_module_sidebars()
	return {
		"module_sidebars": module_sidebars,
		"entity_module": build_entity_module_map(module_sidebars),
		**extra,
	}


@frappe.whitelist()
def save_sidebar_customization(
	module: str, items: list | str | None = None, label: str | None = None, header_icon: str | None = None
):
	"""Save the session user's arrangement of a module's sidebar.

	`items` is the whole ordered arrangement the client is showing, the shape a Sortable produces,
	not a delta. A row naming a base item carries `key` plus whatever the user overrode; a row the
	user added carries `added: 1` and the item itself. If `items` is omitted the arrangement is
	left as it is, which is what lets the header be renamed on its own.
	"""
	return _save_customization(module, items, user=frappe.session.user, label=label, header_icon=header_icon)


@frappe.whitelist()
def save_site_sidebar(
	module: str, items: list | str | None = None, label: str | None = None, header_icon: str | None = None
):
	"""Save the site-wide layer, which applies to every user whose own layer does not override
	it."""
	check_workspace_manager(_("You need to be Workspace Manager to change this for everyone."))
	return _save_customization(module, items, user=None, label=label, header_icon=header_icon)


@frappe.whitelist()
def reset_user_sidebar(module: str):
	"""Drop the user's own layer, falling back to the site layer and then the base."""
	return _reset(module, frappe.session.user)


@frappe.whitelist()
def reset_site_sidebar(module: str):
	check_workspace_manager(_("You need to be Workspace Manager to reset this for everyone."))
	return _reset(module, None)


@frappe.whitelist()
def reset_to_standard(module: str):
	"""Remove every layer from `module`, so it goes back to using its `Sidebar`.

	The other two resets drop one layer and let the next show through. This drops all of them:
	afterwards there is no `Custom Sidebar` for the module, and everyone sees the arrangement the
	app ships, or the computed base for a module no app shipped one for. That is why it is called
	"to Standard" rather than "one layer down". `Workspace` offers the same action under the same
	name and behind the same permission.

	It reaches every user's layer, not just the site's and the caller's. A user whose own
	arrangement survived would not be using the module's `Sidebar`, so the promise would only hold
	for users who had not customized it. The cost is discarding other users' work, which is why
	this confirms before it runs and is behind the right to curate for everyone.

	The rows are deleted one at a time so each layer's `on_trash` runs: a user's own arrangement
	invalidates their boot cache and nobody else's, and only the document knows whose.
	"""
	check_workspace_manager(_("You need to be Workspace Manager to reset this for everyone."))
	check_module(module)

	for name in frappe.get_all("Custom Sidebar", filters={"module": module}, pluck="name"):
		frappe.delete_doc("Custom Sidebar", name, ignore_permissions=True, force=True)

	return module_payload()


def add_site_sidebar_item(module: str, item: dict) -> None:
	"""Append one item to the site-wide layer, leaving the rest unchanged.

	The caller is the system noticing that something on the site needs a way in, such as a
	workspace someone just created. That is site intent, and the base is app content the site
	cannot write to, so it goes here.

	This is not `save_site_sidebar`, which replaces the whole arrangement. That is right when a
	user has just arranged it and wrong when one row is added, because it would drop every
	preference the site had recorded. An item already present is skipped, so the caller does not
	have to check.
	"""
	existing = get_customization(module, None)
	doc = (
		frappe.get_doc("Custom Sidebar", existing.name)
		if existing
		else frappe.new_doc("Custom Sidebar").update({"module": module, "user": SITE_LAYER})
	)

	if any(item_key(row) == item_key(item) for row in doc.sidebar_items):
		return

	doc.append("sidebar_items", {**item, "added": 1})
	# ignore_permissions: creating the workspace is what earned this row, and the arrangement is
	# re-filtered by permissions on every boot whatever is stored here.
	doc.save(ignore_permissions=True)


def _save_customization(
	module: str,
	items: list | str | None,
	user: str | None,
	label: str | None = None,
	header_icon: str | None = None,
):
	check_module(module)

	doc = get_customization(module, user)
	if doc:
		doc = frappe.get_doc("Custom Sidebar", doc.name)
	else:
		doc = frappe.new_doc("Custom Sidebar")
		doc.module = module
		doc.user = user or SITE_LAYER

	if label is not None:
		doc.label = label
	if header_icon is not None:
		doc.header_icon = header_icon

	if items is not None:
		rows = [shape_row(row) for row in (frappe.parse_json(items) or [])]
		settle_references(module, rows, user)

		doc.set("sidebar_items", [])
		for row in rows:
			doc.append("sidebar_items", row)

	# ignore_permissions: a user arranging their own sidebar does not need write access to this
	# doctype. Only their own layer is touched, and the arrangement is re-filtered by permissions
	# on every boot whatever is stored here.
	doc.save(ignore_permissions=True)

	return module_payload()


def shape_row(row: dict) -> dict:
	"""Narrow one row of a saved arrangement to what its kind may carry.

	A reference keeps what names the item it refers to, which is its link columns or the `key` it
	was shown for a row with no link, plus what the arrangement says about it (`hidden` and
	`child`) and the two fields a user can override. Everything else the client echoed back is
	dropped rather than stored.

	That is what prevents the failure that ruled out full-body storage: a stored body carries the
	label, icon, link and filters whether or not the user changed them, so one reorder would
	freeze the site's and the app's values forever.

	The link columns are not a body. They are the row's identity, kept in real columns so a rename
	repairs the reference and the base item it names in one statement.
	"""
	shaped = {
		**{field: row.get(field) for field in LINKED_IDENTITY_FIELDS},
		"key": row.get("key"),
		"hidden": int(row.get("hidden") or 0),
		"added": int(row.get("added") or 0),
		**{field: row.get(field) for field in REFERENCE_FIELDS},
	}

	if shaped["added"]:
		shaped.update({field: row.get(field) for field in ADDED_ITEM_FIELDS})
		# The boot payload calls this `tab`; the row uses the base row's column name.
		shaped["navigate_to_tab"] = row.get("navigate_to_tab") or row.get("tab")

	# Which section the row is in, set last so one statement covers both kinds of row. It is kept
	# for every kind, because where an entry sits is arrangement and every row of a saved
	# arrangement carries its own.
	shaped["child"] = int(row.get("child") or 0)

	return shaped


def settle_references(module: str, rows: list[dict], user: str | None) -> None:
	"""Resolve what the layer being saved was looking at and settle its references against it:
	first what each row names, then what it actually overrides.

	One base resolution serves both steps, and an arrangement of nothing but added items needs
	none. It runs when a user saves, not when the desk boots.

	Hidden items are kept in that resolution rather than dropped, because a save may name one: the
	editor shows what a lower layer hid so it can be brought back. A row bringing one back names
	an item that exists, so it should be anchored by its columns, and the label it echoed back
	should be recognised as inherited rather than stored as this user's override.
	"""
	references = [row for row in rows if not row["added"]]
	if not references:
		return

	resolved, _hidden = resolve_arrangement(base_items(module), layers_below(module, user))
	shown = {item_key(item): item for item in resolved}
	anchor_references(references, shown)
	drop_inherited_values(references, shown)


def anchor_references(rows: list[dict], shown: dict[str, dict]) -> None:
	"""Store each reference the way the model names the item it refers to.

	A client may name an item in any of several ways, echoing the whole row back or sending only
	the `key` the payload gave it. What gets stored is canonical either way: a linked item's own
	columns, so a rename repairs the reference and the base row in one statement, or an unlinked
	item's key, since it has no columns to be named by.

	A reference to something the saver was not shown is stored as it arrived. It names an item
	that is not there and stops applying, which is also what an app deleting an item does to a
	delta that named it.
	"""
	for row in rows:
		item = shown.get(item_key(row))
		if not item:
			continue

		row["type"] = item.get("type")
		if is_linked(item):
			row.update({field: item.get(field) for field in LINKED_IDENTITY_FIELDS})
			row["key"] = None
		else:
			# Nothing to point at, so the columns are cleared and the key carries the identity.
			row.update(dict.fromkeys(("link_type", "link_to", "url")))
			row["key"] = item_key(item)


def drop_inherited_values(rows: list[dict], shown: dict[str, dict]) -> None:
	"""Blank any field a reference row only echoes back from the layer below it.

	The client sends the arrangement it is showing, which carries the labels and icons it was
	given. Stored as-is those would become overrides rather than inheritance: an item the user
	never touched would keep the label it had when they reordered, and neither the site's relabel
	nor the app's would reach them again. A value equal to what the user was shown is not an
	override.
	"""
	for row in rows:
		item = shown.get(item_key(row)) or {}
		for field in REFERENCE_FIELDS:
			value = item.get(field)
			if row.get(field) and row[field] in (value, _(value) if value else None):
				row[field] = None


def layers_below(module: str, user: str | None) -> list["CustomSidebar"]:
	"""Return the layers already applied to what the layer being saved was shown."""
	return get_layers(module, None) if user else []


def base_items(module: str) -> list[dict]:
	"""Return the module's base rows, unfiltered.

	They are not permission-filtered on purpose. These rows are only compared against, so an item
	the saver cannot see never matches a row they sent.
	"""
	from frappe.desk.doctype.sidebar.sidebar import get_module_base

	return [dict(row) for row in get_module_base(module).rows]


def _reset(module: str, user: str | None):
	doc = get_customization(module, user)
	if doc:
		frappe.delete_doc("Custom Sidebar", doc.name, ignore_permissions=True, force=True)
	return module_payload()


# ---------------------------------------------------------------------------------------
# Who may touch which layer
# ---------------------------------------------------------------------------------------


def has_permission(doc, ptype="read", user=None, debug=False):
	"""Allow a Workspace Manager to curate the site; everyone else gets only their own layer.

	This is the document-level half of the gate the endpoints hold. Without it a plain Desk User
	could write the site layer from the form and turn one user's preference into everyone's
	navigation.
	"""
	user = user or frappe.session.user
	if user == "Administrator" or is_workspace_manager(user):
		return True

	return bool(doc.user) and doc.user == user


def get_permission_query_conditions(user=None):
	"""Restrict list queries so everyone but a Workspace Manager sees only their own layer.

	It also keeps one user's preferences out of everyone else's reads, since reports, the API and
	the desk's export all go through it.
	"""
	user = user or frappe.session.user
	if user == "Administrator" or is_workspace_manager(user):
		return ""

	return f"`tabCustom Sidebar`.`user` = {frappe.db.escape(user)}"
