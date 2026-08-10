# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# Cached set of `(module, user)` pairs that have a customization, so the boot path can skip a
# DB hit for the overwhelming majority that have none. Same trick as Workspace Customization.
CUSTOMIZED_KEYS_CACHE_KEY = "customized_module_sidebars"

SITE_LAYER = ""


class ModuleSidebarCustomization(Document):
	_DOCTYPE_NAME = "Module Sidebar Customization"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.module_sidebar_item.module_sidebar_item import ModuleSidebarItem
		from frappe.desk.doctype.module_sidebar_item_preference.module_sidebar_item_preference import (
			ModuleSidebarItemPreference,
		)
		from frappe.types import DF

		added_items: DF.Table[ModuleSidebarItem]
		header_icon: DF.Icon | None
		items: DF.Table[ModuleSidebarItemPreference]
		label: DF.Data | None
		module: DF.Link
		user: DF.Link | None
	# end: auto-generated types

	def validate(self):
		self.validate_unique()

	def validate_unique(self):
		existing = frappe.db.exists(
			"Module Sidebar Customization",
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

	def on_update(self):
		self.clear_customization_cache()

	def on_trash(self):
		self.clear_customization_cache()

	def clear_customization_cache(self):
		frappe.cache.delete_value(CUSTOMIZED_KEYS_CACHE_KEY)
		if self.user:
			# a user-scoped delta only invalidates that user's boot
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
			for row in frappe.get_all("Module Sidebar Customization", fields=["module", "user"])
		]
		frappe.cache.set_value(CUSTOMIZED_KEYS_CACHE_KEY, keys)
	return {tuple(k) for k in keys}


def get_customization(module: str, user: str | None) -> "ModuleSidebarCustomization | None":
	"""The customization for one layer, or None. Cheap when there is none."""
	layer = user or SITE_LAYER
	if (module, layer) not in get_customized_keys():
		return None

	name = frappe.db.exists(
		"Module Sidebar Customization", {"module": module, "user": layer or ["in", ["", None]]}
	)
	return frappe.get_cached_doc("Module Sidebar Customization", name) if name else None


def get_layers(module: str, user: str) -> list["ModuleSidebarCustomization"]:
	"""The deltas to apply, in order: site first, then the user's own.

	Later layers win, so a user's `hidden: 0` un-hides something the site hid -- a preference
	beating a preference, which is what a per-user layer is for.
	"""
	return [layer for layer in (get_customization(module, None), get_customization(module, user)) if layer]


def apply_customizations(module: str, items: list[dict], user: str) -> tuple[list[dict], bool]:
	"""Apply the site and user deltas to a module's already-filtered item list.

	Runs **after** permission filtering, deliberately: a delta can then never resurface an item
	the user may not see, and an added item still has to pass the same check before it lands
	here. Returns `(items, customized)`.

	Unknown keys are silently skipped rather than errored. That is what makes an app
	re-authoring its sidebar non-fatal -- some deltas survive by coincidence, the rest simply
	stop applying.
	"""
	layers = get_layers(module, user)
	if not layers:
		return items, False

	hidden: set[str] = set()
	overrides: dict[str, dict] = {}
	order: dict[str, int] = {}
	added: list[dict] = []

	for layer in layers:
		for idx, pref in enumerate(layer.items):
			if not pref.item_key:
				continue
			# a later layer's explicit value wins, including un-hiding
			if pref.hidden:
				hidden.add(pref.item_key)
			else:
				hidden.discard(pref.item_key)
			if pref.label or pref.icon:
				override = overrides.setdefault(pref.item_key, {})
				if pref.label:
					override["label"] = pref.label
				if pref.icon:
					override["icon"] = pref.icon
			order[pref.item_key] = idx

		for item in layer.added_items:
			added.append(shape_added_item(item))

	resolved = []
	for item in items:
		key = item.get("key")
		if key in hidden:
			continue
		if key in overrides:
			item = {**item, **overrides[key]}
		resolved.append(item)

	resolved.extend(added)

	# Items the user never arranged keep their base order and follow the ones they did, so an
	# app adding an item still surfaces for someone who has already reordered.
	if order:
		resolved.sort(key=lambda i: order.get(i.get("key"), len(order) + 1))

	return resolved, True


def shape_added_item(item) -> dict:
	"""An added row, in the same shape the boot payload uses for a base item."""
	return {
		"key": item.key or f"added-{item.name}",
		"label": _(item.label),
		"link_to": item.link_to,
		"link_type": item.link_type,
		"type": item.type,
		"icon": item.icon,
		"child": item.child,
		"collapsible": item.collapsible,
		"indent": item.indent,
		"keep_closed": item.keep_closed,
		"url": item.url,
		"show_arrow": item.show_arrow,
		"filters": item.filters,
		"route_options": item.route_options,
		"tab": item.navigate_to_tab,
		"open_in_new_tab": item.open_in_new_tab,
		"default_workspace": item.default_workspace,
		"added": 1,
	}


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
def save_sidebar_customization(module: str, items: list | str, added_items: list | str | None = None):
	"""Save the session user's arrangement of a module's sidebar.

	`items` is the whole ordered arrangement the client is showing -- the shape a Sortable
	produces -- not a delta: `[{"item_key": ..., "hidden": 0, "label": ..., "icon": ...}, ...]`.
	"""
	return _save_customization(module, items, added_items, user=frappe.session.user)


@frappe.whitelist()
def save_site_sidebar(module: str, items: list | str, added_items: list | str | None = None):
	"""Save the site-wide layer, which applies to everyone a user delta does not override."""
	if not is_workspace_manager():
		frappe.throw(
			_("You need to be Workspace Manager to change this for everyone."),
			frappe.PermissionError,
		)
	return _save_customization(module, items, added_items, user=None)


@frappe.whitelist()
def reset_user_sidebar(module: str):
	"""Drop the user's own delta, falling back to the site layer and then the base."""
	return _reset(module, frappe.session.user)


@frappe.whitelist()
def reset_site_sidebar(module: str):
	if not is_workspace_manager():
		frappe.throw(
			_("You need to be Workspace Manager to reset this for everyone."),
			frappe.PermissionError,
		)
	return _reset(module, None)


def _save_customization(module, items, added_items, user):
	# The module, not its sidebar: most modules have no `Module Sidebar` document at all --
	# their base is computed from their contents -- and those are customizable on exactly the
	# same terms as a shipped one. What has to exist is the thing the delta is anchored to.
	if not frappe.db.exists("Module Def", module):
		frappe.throw(_("{0} is not a module.").format(module))

	items = frappe.parse_json(items) or []
	added_items = frappe.parse_json(added_items) or []

	doc = get_customization(module, user)
	if doc:
		doc = frappe.get_doc("Module Sidebar Customization", doc.name)
	else:
		doc = frappe.new_doc("Module Sidebar Customization")
		doc.module = module
		doc.user = user or SITE_LAYER

	doc.set("items", [])
	for row in items:
		if not row.get("item_key"):
			continue
		doc.append(
			"items",
			{
				"item_key": row.get("item_key"),
				"hidden": int(row.get("hidden") or 0),
				"label": row.get("label"),
				"icon": row.get("icon"),
			},
		)

	doc.set("added_items", [])
	for row in added_items:
		doc.append("added_items", row)

	# ignore_permissions: a user arranging their own sidebar need not hold write access to
	# this doctype. Only their own layer is touched, and the arrangement is re-filtered
	# through permissions on every boot regardless of what is stored here.
	doc.save(ignore_permissions=True)

	return module_payload()


def _reset(module, user):
	doc = get_customization(module, user)
	if doc:
		frappe.delete_doc("Module Sidebar Customization", doc.name, ignore_permissions=True, force=True)
	return module_payload()


def is_workspace_manager() -> bool:
	return "Workspace Manager" in frappe.get_roles()
