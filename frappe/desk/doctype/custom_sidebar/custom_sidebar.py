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

# What a row carries when it *is* an item rather than a reference to one. The same fields a
# base item has, because an added item renders through the same code with no special-casing --
# with one exception: `is_default_module`. Apps claim, sites do not.
#
# Ownership is an app-authored fact about a product, not a site preference, and the layer here
# is one-way: a site could add a flagged row to claim an entity, but there is no reference field
# that could ever un-claim one an app shipped (`REFERENCE_FIELDS` is `label` and `icon`). Leaving
# it in would offer half a mechanism. A site that disagrees about where an entity lives edits the
# sidebar so the entity is a member of the one it wants -- membership is what routes you.
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

# What a *reference* row may say about the base item it names. Deliberately short: a reference
# stores an opinion, never a copy. Storing the whole body is what would let one reorder freeze
# the site's labels and the app's links forever.
REFERENCE_FIELDS = ("label", "icon")


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
		"""A layer is anchored to a module, and this says so in the model rather than leaving it
		to the endpoints -- `_validate_links` below no longer checks this document's own Link
		fields either, so nothing else would."""
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
		"""No layer stores a row naming a private workspace -- not the site's, not a user's own.

		A private page's link is derived on read (`sidebar.get_private_workspaces`), and the
		derivation is appended to the arrangement the client is shown, so it comes back with
		that arrangement on the next save. Kept, it would be exactly the pollution D3 removes:
		a row per private page in the document the whole site shares, or -- in the owner's own
		layer -- a second copy of a link that is already derived from the workspace, left
		pointing nowhere the day the page is deleted.

		Enforced here rather than in the endpoints because every write is a way in: the two save
		endpoints, `add_site_sidebar_item`, the form, the API. It also retires the rows a site
		stored before the derivation existed -- the next save of that layer takes them out.

		A *public* workspace is untouched: its link is stored, and arranging or hiding it is
		what the layers are for.
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
		"""Every row has to name a base item, and name it the way the model names one.

		A reference naming nothing -- no link, no key -- is dropped rather than given a derived
		one: a derived identity would be a coincidence, and coinciding with a real base item is
		worse than saying nothing. An added row *is* an item and names itself, out of the same
		columns a base item is named by. Nothing is ever anchored to a row's `name`: child rows
		are hash-named and recreated on every save.

		A linked row's stored key is blanked on the way in. Its columns are its identity, and a
		rename rewrites them for base and delta together -- a key stored beside them would
		survive that rename still naming what the row used to point at.
		"""
		self.set(
			"sidebar_items",
			[row for row in self.sidebar_items if row.added or is_linked(row) or row.key],
		)
		for row in self.sidebar_items:
			if is_linked(row):
				row.key = None

	def _validate_links(self):
		"""A row *names* a document; it does not reference one.

		Frappe checks a Dynamic Link's target still exists on every save, which here would mean
		one deleted report turning every later write to this layer into an error -- relabelling
		the sidebar, a new workspace adding its link, anything. A row naming something that is
		gone stops applying when the sidebar resolves, which is exactly what an app deleting an
		item has always done to a delta that named it.

		`ignore_links_on_delete` in hooks is the same call made from the other side of the same
		link: nobody's sidebar preference may stop a document being deleted either.
		"""
		return

	def on_update(self):
		self.clear_customization_cache()

	def on_trash(self):
		self.clear_customization_cache()

	def clear_customization_cache(self):
		if self.user:
			# a user-scoped arrangement only invalidates that user's boot
			frappe.cache.hdel("bootinfo", self.user)
		else:
			frappe.cache.delete_key("bootinfo")


def get_layers_for(user: str, modules: list[str] | None = None) -> dict[str, list["CustomSidebar"]]:
	"""Every layer that applies to `user`, keyed by module and in the order they are applied.

	**Which layers apply is a question about the reader, not about a module** -- the site's, and
	their own -- so it is answered once for however many modules are being resolved. That is the
	same batching `SidebarContext` already does for the bases, the workspaces and the
	onboardings, and this is the fourth of those reads rather than an exception to them.

	One indexed query. It replaces a site-wide redis set of every `(module, user)` pair on the
	site, read in full on every boot to gate a per-module `db.exists`. That set answered the
	right question keyed by the wrong thing: it grew with users x modules, so a site with five
	thousand people who had each arranged three modules deserialized fifteen thousand pairs to
	decide something about one of them -- and it needed invalidating, which is a second way to
	be wrong. What a reader's own layers cost is now a function of how much *they* have
	customized, which is the dimension that belongs in the answer.
	"""
	filters = {"user": ["in", [SITE_LAYER, user]]}
	if modules is not None:
		filters["module"] = ["in", modules]

	rows = frappe.get_all("Custom Sidebar", filters=filters, fields=["name", "module", "user"])
	# The site's layer first, then the reader's own. Stated here rather than left to the column's
	# sort order: a blank `user` collating before an email address is a fact about the database,
	# and the application order is not.
	rows.sort(key=lambda row: bool(row.user))

	layers: dict[str, list[CustomSidebar]] = {}
	for row in rows:
		layers.setdefault(row.module, []).append(frappe.get_cached_doc("Custom Sidebar", row.name))

	return layers


def get_customization(module: str, user: str | None) -> "CustomSidebar | None":
	"""The customization for one layer, or None.

	For one module and one layer, which is what the write paths ask. A resolution covering many
	modules asks `get_layers_for` once instead of asking this per module.
	"""
	name = frappe.db.exists("Custom Sidebar", {"module": module, "user": user or ["in", ["", None]]})
	return frappe.get_cached_doc("Custom Sidebar", name) if name else None


def get_layers(module: str, user: str | None) -> list["CustomSidebar"]:
	"""The layers to apply to `module`, in order: the site's first, then the user's own.

	Later layers win, so a user's `hidden: 0` un-hides something the site hid -- a preference
	beating a preference, which is what a per-user layer is for.

	`user` of `None` means the site's layer alone. It used to mean the site's layer *twice* --
	`get_customization(module, None)` and `get_customization(module, user)` both resolve to it --
	which the merge happened to survive, being idempotent, but which is not what any caller
	asked for.
	"""
	layers = [get_customization(module, None)]
	if user:
		layers.append(get_customization(module, user))

	return [layer for layer in layers if layer]


def check_module(module: str) -> None:
	"""A layer is anchored to a module, so nothing may name one that is not there.

	The module, not its sidebar: most modules have no `Sidebar` document at all -- their base is
	computed from their contents -- and those are customizable, readable and resettable on
	exactly the same terms as a shipped one. What has to exist is the thing the layer is
	anchored to.
	"""
	if not frappe.db.exists("Module Def", module):
		frappe.throw(_("{0} is not a module.").format(module))


# ---------------------------------------------------------------------------------------
# The merge engine
# ---------------------------------------------------------------------------------------


def resolve_arrangement(
	items: list[dict], layers: list["CustomSidebar"]
) -> tuple[list[dict], dict[str, bool]]:
	"""Fold each layer into `items`, in order, and hand back what came out and what is hidden.

	The merge itself is `frappe.desk.layers`, which the dock resolves through too. What is the
	sidebar's own is the two things handed over here -- how an item is identified (`item_key`)
	and what a row does to the item it names (`apply_sidebar_row`).

	What to do about a hidden item is left to the caller, because the sidebar has two callers
	that answer it differently: what renders drops one (`merge_layers`), and what the editor
	opens on keeps it (`layer_arrangement`), since an editor that cannot see a hidden item
	cannot offer to bring it back.
	"""
	return resolve_layers(
		items,
		[layer.sidebar_items for layer in layers],
		key=item_key,
		apply_row=apply_sidebar_row,
	)


def merge_layers(items: list[dict], layers: list["CustomSidebar"]) -> list[dict]:
	"""The arrangement as it renders: an item left hidden across all the layers is *removed*,
	rather than rendered as hidden the way the dock renders one."""
	resolved, hidden = resolve_arrangement(items, layers)

	return [item for item in resolved if not hidden.get(item_key(item))]


def apply_sidebar_row(row, item: dict | None) -> dict | None:
	"""What one customization row does to the base item it names.

	An `added` row *is* an item, so it stands in for whatever the list holds under that key --
	usually nothing. A reference row states an opinion about an item that is already there, and
	`overrides` keeps that opinion short: a reference stores an opinion, never a copy.

	A reference naming an item the list does not hold returns `None` and is skipped rather than
	errored. That is what makes an app re-authoring its sidebar non-fatal -- some rows survive by
	coincidence, the rest simply stop applying -- and it is the same answer for a row naming an
	item this user may not see, since the layers are applied after permission filtering.
	"""
	if row.added:
		return shape_added_item(row)

	return {**item, **overrides(row)} if item is not None else None


def overrides(row) -> dict:
	"""What a reference row says about the item it names. An empty field is no opinion."""
	return {field: row.get(field) for field in REFERENCE_FIELDS if row.get(field)}


def shape_added_item(row) -> dict:
	"""An added row, in the shape the boot payload uses for a base item."""
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
# One endpoint per layer, each carrying its own gate, the way the dock's reads and this
# module's saves and resets do -- a single endpoint taking "which layer" would carry the gate
# in a branch instead.
# ---------------------------------------------------------------------------------------


def layer_arrangement(module: str, user: str | None) -> list[dict]:
	"""`module`'s sidebar as one layer arranges it, with hidden items kept.

	What the editor opens on, and neither of the two answers that already exist. The boot
	payload is the resolution for the reader, which drops a hidden item -- and an editor that
	cannot see one cannot offer to bring it back. A layer's stored rows are a delta, and this
	editor saves the whole arrangement rather than a delta.

	The layer being edited is included, so what comes back is the arrangement as it stands. An
	*unarranged* layer therefore reads as **the layer below it, as that layer renders** -- the
	rule the editor needs, got here rather than seeded in the client: a save writes the whole
	arrangement, so starting from anything else would silently un-hide what a lower layer hid.

	`added` names only this layer's own added rows. An item a layer below added is a *reference*
	from here, and saying otherwise would copy its body into this layer and freeze the label,
	icon and link the layer below still owns -- the same failure `REFERENCE_FIELDS` exists to
	prevent.

	The two layers disagree about the permission filter, the way the dock's two reads do. A
	person's own arrangement is what is in front of *them*, so it is filtered. The site's is
	not: who may see an item is a fact about the reader, applied to what each person boots, so
	it is no part of what the site arranged -- and a curator handed a filtered screen would drop
	the site's rows for everything they personally cannot see on the very next save, since this
	editor writes the whole arrangement.

	Private workspaces are absent, as they are from every stored arrangement: they are derived
	after the merge, and `drop_private_workspaces` takes them back out of anything storing one.
	"""
	from frappe.desk.doctype.sidebar.sidebar import filter_sidebar_items, get_sidebar_bases

	check_module(module)

	base = get_sidebar_bases([module])[module]
	# `is_item_allowed` is a method on `DeskViews`, so the check needs an instance to run on --
	# one throwaway `Workspace`, exactly as `SidebarContext` builds for the boot.
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
	"""How this person has `module`'s sidebar arranged. No gate: it is theirs."""
	return layer_arrangement(module, frappe.session.user)


@frappe.whitelist()
def get_site_sidebar_layer(module: str) -> list[dict]:
	check_workspace_manager(_("You need to be Workspace Manager to see the sidebar's site layer."))
	return layer_arrangement(module, None)


# ---------------------------------------------------------------------------------------
# Write API
# ---------------------------------------------------------------------------------------


def module_payload(**extra) -> dict:
	"""The desk state a customization write invalidates, for the client to swap in place."""
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

	`items` is the whole ordered arrangement the client is showing -- the shape a Sortable
	produces -- not a delta. A row naming a base item carries `key` and whatever the user has
	an opinion about; a row the user added carries `added: 1` and the item itself. Omitted, the
	arrangement is left as it stands, which is what lets the header be renamed on its own.
	"""
	return _save_customization(module, items, user=frappe.session.user, label=label, header_icon=header_icon)


@frappe.whitelist()
def save_site_sidebar(
	module: str, items: list | str | None = None, label: str | None = None, header_icon: str | None = None
):
	"""Save the site-wide layer, which applies to everyone a user's own layer does not override."""
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


def add_site_sidebar_item(module: str, item: dict) -> None:
	"""Append one item to the site-wide layer, leaving the rest of it alone.

	The caller for this is the system noticing that something on the site needs a way in --
	a workspace someone just created. That is site intent, and the base is app content the site
	may not write to, so it lands here.

	Not `save_site_sidebar`, which replaces the whole arrangement: right when a person has just
	arranged it, wrong when one row is being added, because it would drop every preference the
	site had recorded. Skips an item already present, so the caller need not remember.
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
	# ignore_permissions: creating a workspace is what earned this row, and the arrangement is
	# re-filtered through permissions on every boot regardless of what is stored here
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

	# ignore_permissions: a user arranging their own sidebar need not hold write access to
	# this doctype. Only their own layer is touched, and the arrangement is re-filtered
	# through permissions on every boot regardless of what is stored here.
	doc.save(ignore_permissions=True)

	return module_payload()


def shape_row(row: dict) -> dict:
	"""One row of a saved arrangement, narrowed to what its kind is allowed to carry.

	A reference keeps what names the item it refers to -- its link columns, or the `key` it was
	shown for a row that has no link -- plus `hidden` and the two fields a person can have an
	opinion about. Everything else the client echoed back is dropped here rather than stored.
	That is the whole defence against the failure mode that killed full-body storage -- a
	stored body carries the label, icon, link and filters whether or not the user has a view on
	them, so one reorder would freeze the site's and the app's forever.

	The link columns are not a body: they are the row's identity, kept in real columns so a
	rename repairs the reference and the base item it names in the same statement.
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
		# the boot payload calls it `tab`; the row calls it what the base row calls it
		shaped["navigate_to_tab"] = row.get("navigate_to_tab") or row.get("tab")

	return shaped


def settle_references(module: str, rows: list[dict], user: str | None) -> None:
	"""Resolve what the layer being saved was looking at, and settle its references against it:
	what each row *names*, and then what it actually *says*.

	One base resolution for both, and none at all for an arrangement of nothing but added items
	-- and it happens when a person clicks, not when the desk boots.

	Hidden items are kept in that resolution rather than dropped. A save may name one: the
	editor shows what a layer below hid so it can be brought back, and a row bringing one back
	is naming an item that is really there -- so it deserves to be anchored by its columns, and
	the label it echoed back deserves to be recognised as inherited rather than stored as this
	person's opinion of it.
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

	A client may name an item however it likes -- echoing the whole row back, or sending only
	the `key` the payload gave it. What gets *stored* is canonical either way: a linked item's
	own columns, so that a rename repairs the reference and the base row together in one
	statement; an unlinked item's key, since it has no columns to be named by.

	A reference to something not in front of the saver is left exactly as it arrived. It names
	an item that is not there and simply stops applying -- which is also what an app deleting
	an item does to a delta that survived it.
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
			# nowhere to point, so the columns say nothing and the key says everything
			row.update(dict.fromkeys(("link_type", "link_to", "url")))
			row["key"] = item_key(item)


def drop_inherited_values(rows: list[dict], shown: dict[str, dict]) -> None:
	"""Blank out what a reference row only echoes back from the layer below it.

	The client sends the arrangement it is *showing*, which carries the labels and icons it was
	given. Stored as-is they would stop being inheritance and start being opinion: an item the
	user never touched would keep the label it happened to have on the day they reordered, and
	neither the site's relabel nor the app's would ever reach them again. Equal to what they
	were shown means they said nothing.
	"""
	for row in rows:
		item = shown.get(item_key(row)) or {}
		for field in REFERENCE_FIELDS:
			value = item.get(field)
			if row.get(field) and row[field] in (value, _(value) if value else None):
				row[field] = None


def layers_below(module: str, user: str | None) -> list["CustomSidebar"]:
	"""The layers already applied to what the layer being saved was shown."""
	return get_layers(module, None) if user else []


def base_items(module: str) -> list[dict]:
	"""The module's base rows, unfiltered.

	Not permission-filtered, and not meant to be: this is only ever compared against, so an
	item the saver cannot see simply never matches a row they sent.
	"""
	from frappe.desk.doctype.sidebar.sidebar import get_sidebar_bases

	return [dict(row) for row in get_sidebar_bases([module])[module].rows]


def _reset(module: str, user: str | None):
	doc = get_customization(module, user)
	if doc:
		frappe.delete_doc("Custom Sidebar", doc.name, ignore_permissions=True, force=True)
	return module_payload()


# ---------------------------------------------------------------------------------------
# Who may touch which layer
# ---------------------------------------------------------------------------------------


def has_permission(doc, ptype="read", user=None, debug=False):
	"""A Workspace Manager curates the site; everyone else has only their own layer.

	The document-level half of the same gate the endpoints hold: without it a plain Desk User
	could write the site layer straight from the form and make one person's preference into
	everybody's navigation.
	"""
	user = user or frappe.session.user
	if user == "Administrator" or is_workspace_manager(user):
		return True

	return bool(doc.user) and doc.user == user


def get_permission_query_conditions(user=None):
	"""Everyone but a Workspace Manager lists only their own layer.

	This is also what keeps one person's preferences out of everybody else's reads -- reports,
	the API and the desk's export all go through it.
	"""
	user = user or frappe.session.user
	if user == "Administrator" or is_workspace_manager(user):
		return ""

	return f"`tabCustom Sidebar`.`user` = {frappe.db.escape(user)}"
