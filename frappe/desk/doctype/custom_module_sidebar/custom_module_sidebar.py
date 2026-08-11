# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.desk.doctype.module_sidebar.module_sidebar import assign_keys
from frappe.model.document import Document

# Cached set of `(module, user)` pairs that have a customization, so the boot path can skip a
# DB hit for the overwhelming majority that have none. Same trick as Workspace Customization.
CUSTOMIZED_KEYS_CACHE_KEY = "customized_module_sidebars"

SITE_LAYER = ""

# What a row carries when it *is* an item rather than a reference to one. The same fields a
# base item has, because an added item renders through the same code with no special-casing.
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
	"default_workspace",
)

# What a *reference* row may say about the base item it names. Deliberately short: a reference
# stores an opinion, never a copy. Storing the whole body is what would let one reorder freeze
# the site's labels and the app's links forever.
REFERENCE_FIELDS = ("label", "icon")


class CustomModuleSidebar(Document):
	_DOCTYPE_NAME = "Custom Module Sidebar"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.module_sidebar_item.module_sidebar_item import ModuleSidebarItem
		from frappe.types import DF

		header_icon: DF.Icon | None
		label: DF.Data | None
		module: DF.Link
		sidebar_items: DF.Table[ModuleSidebarItem]
		user: DF.Link | None
	# end: auto-generated types

	def validate(self):
		self.validate_unique()
		self.key_the_items()

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

	def key_the_items(self):
		"""Every row is matched to a base item by `key`, so every row needs one.

		A reference with no key names nothing, so it is dropped rather than given a derived one
		-- a derived key would be a coincidence, and coinciding with a real base item is worse
		than saying nothing. An added row *is* an item and gets its key from the same derivation
		base items use, which is what keeps it identifiable across saves: the child rows are
		hash-named and recreated on every save, so anything anchored to a row name would come
		loose the first time somebody else's layer was written.
		"""
		self.set("sidebar_items", [row for row in self.sidebar_items if row.added or row.key])
		assign_keys(self.sidebar_items)

	def on_update(self):
		self.clear_customization_cache()

	def on_trash(self):
		self.clear_customization_cache()

	def clear_customization_cache(self):
		frappe.cache.delete_value(CUSTOMIZED_KEYS_CACHE_KEY)
		if self.user:
			# a user-scoped arrangement only invalidates that user's boot
			frappe.cache.hdel("bootinfo", self.user)
		else:
			frappe.cache.delete_key("bootinfo")


def get_customized_keys() -> set[tuple[str, str]]:
	"""Cached `(module, user)` pairs carrying a customization.

	This is the whole cost-control story: an uncustomized site pays one redis read on boot
	instead of a query per module.
	"""
	keys = frappe.cache.get_value(CUSTOMIZED_KEYS_CACHE_KEY)
	if keys is None:
		keys = [
			(row.module, row.user or SITE_LAYER)
			for row in frappe.get_all("Custom Module Sidebar", fields=["module", "user"])
		]
		frappe.cache.set_value(CUSTOMIZED_KEYS_CACHE_KEY, keys)
	return {tuple(k) for k in keys}


def get_customization(module: str, user: str | None) -> "CustomModuleSidebar | None":
	"""The customization for one layer, or None. Cheap when there is none."""
	layer = user or SITE_LAYER
	if (module, layer) not in get_customized_keys():
		return None

	name = frappe.db.exists("Custom Module Sidebar", {"module": module, "user": layer or ["in", ["", None]]})
	return frappe.get_cached_doc("Custom Module Sidebar", name) if name else None


def get_layers(module: str, user: str | None) -> list["CustomModuleSidebar"]:
	"""The layers to apply, in order: the site's first, then the user's own.

	Later layers win, so a user's `hidden: 0` un-hides something the site hid -- a preference
	beating a preference, which is what a per-user layer is for.
	"""
	return [layer for layer in (get_customization(module, None), get_customization(module, user)) if layer]


# ---------------------------------------------------------------------------------------
# The merge engine
# ---------------------------------------------------------------------------------------


def apply_customizations(module: str, items: list[dict], user: str) -> tuple[list[dict], bool]:
	"""Apply the site and user layers to a module's already-filtered item list.

	Runs **after** permission filtering, deliberately: a layer can then never resurface an item
	the user may not see, and an added item still has to pass the same check before it lands
	here. Returns `(items, customized)`.
	"""
	layers = get_layers(module, user)
	if not layers:
		return items, False

	return merge_layers(items, layers), True


def merge_layers(items: list[dict], layers: list["CustomModuleSidebar"]) -> list[dict]:
	"""Fold each layer into `items`, in order, and drop what is left hidden.

	Hiding is resolved across all the layers before anything is removed rather than layer by
	layer, which is what makes un-hiding possible at all: a user's `hidden: 0` has to find the
	item the site hid still in the list to say anything about it.

	Unknown keys are silently skipped rather than errored. That is what makes an app
	re-authoring its sidebar non-fatal -- some rows survive by coincidence, the rest simply
	stop applying.
	"""
	resolved = [dict(item) for item in items]
	hidden: dict[str, bool] = {}

	for layer in layers:
		resolved = apply_layer(resolved, hidden, layer)

	return [item for item in resolved if not hidden.get(item.get("key"))]


def apply_layer(items: list[dict], hidden: dict[str, bool], layer: "CustomModuleSidebar") -> list[dict]:
	"""One layer's arrangement, folded into `items`. Mutates `hidden`, which spans the layers."""
	by_key = {item.get("key"): item for item in items}
	arranged: list[str] = []

	for row in layer.sidebar_items:
		# a key named twice is a client sending the same item twice; the first position wins,
		# because the alternative is rendering the item twice
		if not row.key or row.key in arranged:
			continue

		if row.added:
			by_key[row.key] = shape_added_item(row)
		elif row.key in by_key:
			by_key[row.key] = {**by_key[row.key], **overrides(row)}
		else:
			# an item the app has since deleted, or one this user may not see: skipped, never
			# raised, and never conjured into the list
			continue

		hidden[row.key] = bool(row.hidden)
		arranged.append(row.key)

	# Items the layer never named keep their incoming order and follow the ones it did, so an
	# app adding an item still surfaces for someone who has already reordered.
	seen = set(arranged)
	return [by_key[key] for key in arranged] + [item for item in items if item.get("key") not in seen]


def overrides(row) -> dict:
	"""What a reference row says about the item it names. An empty field is no opinion."""
	return {field: row.get(field) for field in REFERENCE_FIELDS if row.get(field)}


def shape_added_item(row) -> dict:
	"""An added row, in the shape the boot payload uses for a base item."""
	item = {field: row.get(field) for field in ADDED_ITEM_FIELDS}
	item.update(
		{
			"key": row.key,
			"label": _(row.label),
			"tab": row.navigate_to_tab,
			"added": 1,
		}
	)
	return item


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
		frappe.get_doc("Custom Module Sidebar", existing.name)
		if existing
		else frappe.new_doc("Custom Module Sidebar").update({"module": module, "user": SITE_LAYER})
	)

	if any(
		row.added and row.link_type == item.get("link_type") and row.link_to == item.get("link_to")
		for row in doc.sidebar_items
	):
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
	# The module, not its sidebar: most modules have no `Module Sidebar` document at all --
	# their base is computed from their contents -- and those are customizable on exactly the
	# same terms as a shipped one. What has to exist is the thing the layer is anchored to.
	if not frappe.db.exists("Module Def", module):
		frappe.throw(_("{0} is not a module.").format(module))

	doc = get_customization(module, user)
	if doc:
		doc = frappe.get_doc("Custom Module Sidebar", doc.name)
	else:
		doc = frappe.new_doc("Custom Module Sidebar")
		doc.module = module
		doc.user = user or SITE_LAYER

	if label is not None:
		doc.label = label
	if header_icon is not None:
		doc.header_icon = header_icon

	if items is not None:
		rows = [shape_row(row) for row in (frappe.parse_json(items) or [])]
		drop_inherited_values(module, rows, user)

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

	A reference keeps `key`, `hidden` and the two fields a person can have an opinion about;
	everything else the client echoed back is dropped here rather than stored. That is the
	whole defence against the failure mode that killed full-body storage -- a stored body
	carries the label, icon, link and filters whether or not the user has a view on them, so
	one reorder would freeze the site's and the app's forever.
	"""
	shaped = {
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


def drop_inherited_values(module: str, rows: list[dict], user: str | None) -> None:
	"""Blank out what a reference row only echoes back from the layer below it.

	The client sends the arrangement it is *showing*, which carries the labels and icons it was
	given. Stored as-is they would stop being inheritance and start being opinion: an item the
	user never touched would keep the label it happened to have on the day they reordered, and
	neither the site's relabel nor the app's would ever reach them again. Equal to what they
	were shown means they said nothing.
	"""
	references = [row for row in rows if not row.get("added") and row.get("key")]
	if not references:
		return

	inherited = {
		item.get("key"): item for item in merge_layers(base_items(module), layers_below(module, user))
	}

	for row in references:
		shown = inherited.get(row["key"]) or {}
		for field in REFERENCE_FIELDS:
			value = shown.get(field)
			if row.get(field) and row[field] in (value, _(value) if value else None):
				row[field] = None


def layers_below(module: str, user: str | None) -> list["CustomModuleSidebar"]:
	"""The layers already applied to what the layer being saved was shown."""
	return get_layers(module, None) if user else []


def base_items(module: str) -> list[dict]:
	"""The module's base rows, unfiltered.

	Not permission-filtered, and not meant to be: this is only ever compared against, so an
	item the saver cannot see simply never matches a row they sent.
	"""
	from frappe.boot import get_sidebar_bases

	return [dict(row) for row in get_sidebar_bases([module])[module].rows]


def _reset(module: str, user: str | None):
	doc = get_customization(module, user)
	if doc:
		frappe.delete_doc("Custom Module Sidebar", doc.name, ignore_permissions=True, force=True)
	return module_payload()


# ---------------------------------------------------------------------------------------
# Who may touch which layer
# ---------------------------------------------------------------------------------------


def is_workspace_manager(user: str | None = None) -> bool:
	return "Workspace Manager" in frappe.get_roles(user)


def check_workspace_manager(message: str) -> None:
	"""The gate on every site layer.

	`Workspace Manager`, not System Manager: the two roles do not imply each other, and the
	holder of the role literally named for curating navigation is the one who should be
	curating navigation. It is granted to nobody by default, which is a tighter answer to "a
	plain Desk User must not touch the site layer" than System Manager would be.
	"""
	if not is_workspace_manager():
		frappe.throw(message, frappe.PermissionError)


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

	return f"`tabCustom Module Sidebar`.`user` = {frappe.db.escape(user)}"
