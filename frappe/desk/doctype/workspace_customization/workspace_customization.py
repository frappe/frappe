# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from json import dumps, loads

import frappe
from frappe import _
from frappe.model.document import Document

# Block `type` -> Workspace child-table parentfield. Every widget block is matched to
# its child row by the row's `label`, which equals the block's `data["<type>_name"]`
# (the same join `clean_up()` in desk/desktop.py uses).
WIDGET_PARENTFIELD = {
	"card": "links",
	"shortcut": "shortcuts",
	"chart": "charts",
	"quick_list": "quick_lists",
	"number_card": "number_cards",
	"custom_block": "custom_blocks",
}

# Cache key for the set of workspaces that have a customization, so the hot render
# path can skip a DB hit for the (vast) majority of uncustomized workspaces.
CUSTOMIZED_NAMES_CACHE_KEY = "customized_workspace_names"


class WorkspaceCustomization(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.has_role.has_role import HasRole
		from frappe.types import DF

		added_roles: DF.Table[HasRole]
		content_delta: DF.LongText | None
		icon: DF.Data | None
		indicator_color: DF.Literal[
			"",
			"green",
			"cyan",
			"blue",
			"orange",
			"yellow",
			"gray",
			"grey",
			"red",
			"pink",
			"darkgrey",
			"purple",
			"light-blue",
		]
		override_sequence: DF.Check
		removed_roles: DF.Table[HasRole]
		sequence_id: DF.Float
		visibility: DF.Literal["Inherit", "Visible", "Hidden"]
		workspace: DF.Link
	# end: auto-generated types

	def validate(self):
		if not frappe.db.get_value("Workspace", self.workspace, "standard"):
			frappe.throw(_("Only standard (app-shipped) workspaces can be customized."))

	def on_update(self):
		self.clear_cache()

	def on_trash(self):
		self.clear_cache()

	def clear_cache(self):
		# the customization changes a *public* workspace, so bust the shared bootinfo
		# cache the same way Workspace.clear_cache does for public pages.
		frappe.cache.delete_key("bootinfo")
		frappe.cache.delete_value(CUSTOMIZED_NAMES_CACHE_KEY)


def block_key(block: dict) -> str:
	"""Stable semantic identity for a content block, independent of the throwaway editor id."""
	block_type = block.get("type")
	data = block.get("data") or {}
	if block_type in WIDGET_PARENTFIELD:
		ident = data.get(f"{block_type}_name")
	elif block_type == "onboarding":
		ident = data.get("onboarding_name")
	else:
		# structural blocks (header/paragraph/spacer): fall back to text, then editor id
		ident = data.get("text") or block.get("id")
	return f"{block_type}:{ident}"


def get_customized_workspace_names() -> set[str]:
	"""Cached set of workspace names that have a customization."""
	names = frappe.cache.get_value(CUSTOMIZED_NAMES_CACHE_KEY)
	if names is None:
		names = frappe.get_all("Workspace Customization", pluck="workspace")
		frappe.cache.set_value(CUSTOMIZED_NAMES_CACHE_KEY, names)
	return set(names)


def get_customization(workspace: str) -> "WorkspaceCustomization | None":
	"""Return the customization for a workspace, or None. Cheap when uncustomized."""
	if workspace not in get_customized_workspace_names():
		return None
	# customization name == workspace name (autoname: field:workspace)
	try:
		return frappe.get_cached_doc("Workspace Customization", workspace)
	except frappe.DoesNotExistError:
		frappe.clear_last_message()
		return None


def effective_roles(base_roles: list[str], customization: "WorkspaceCustomization") -> list[str]:
	"""(base.roles - removed_roles) | added_roles."""
	removed = {r.role for r in customization.removed_roles}
	roles = {r for r in base_roles if r not in removed}
	roles.update(r.role for r in customization.added_roles)
	return list(roles)


def apply_customization(doc, customization: "WorkspaceCustomization") -> None:
	"""Merge a customization onto a *fresh* (non-cached) Workspace doc, in place.

	The standard record stays the live base: hidden/overridden/reordered blocks reference
	the base by semantic key, so app-removed blocks become silent no-ops, and app-added
	blocks flow through untouched (app owns existence, site owns presentation).
	"""
	_apply_roles(doc, customization)
	_apply_properties(doc, customization)
	_apply_content(doc, customization)


def _apply_roles(doc, customization) -> None:
	new_roles = effective_roles([r.role for r in doc.roles], customization)
	doc.set("roles", [])
	for role in new_roles:
		doc.append("roles", {"role": role})


def _apply_properties(doc, customization) -> None:
	if customization.visibility == "Hidden":
		doc.is_hidden = 1
	elif customization.visibility == "Visible":
		doc.is_hidden = 0
	if customization.icon:
		doc.icon = customization.icon
	if customization.indicator_color:
		doc.indicator_color = customization.indicator_color
	if customization.override_sequence:
		doc.sequence_id = customization.sequence_id


def apply_content_delta(content: list, delta: dict) -> list:
	"""Merge the content delta onto a list of editor.js blocks and return the new list.

	Shared by the doc merge (widget data) and `get_workspaces` (the rendered block layout),
	so both stay in sync. Drops hidden blocks, applies presentation overrides, appends the
	site's added blocks, then reorders -- all keyed on semantic identity.
	"""
	hidden = set(delta.get("hidden_blocks") or [])
	overrides = delta.get("block_overrides") or {}
	order = delta.get("block_order") or []
	added = delta.get("added_blocks") or []

	new_content = []
	for block in content:
		key = block_key(block)
		if key in hidden:
			continue
		if key in overrides:
			block.setdefault("data", {}).update(overrides[key])
		new_content.append(block)

	for entry in added:
		if entry.get("block"):
			new_content.append(entry["block"])

	if order:
		position = {key: idx for idx, key in enumerate(order)}
		new_content.sort(key=lambda block: position.get(block_key(block), len(position)))

	return new_content


def _apply_content(doc, customization) -> None:
	delta = loads(customization.content_delta or "{}")
	hidden = set(delta.get("hidden_blocks") or [])
	overrides = delta.get("block_overrides") or {}
	added = delta.get("added_blocks") or []

	# the rendered block layout
	doc.content = dumps(apply_content_delta(loads(doc.content or "[]"), delta))

	# remove the child rows backing hidden widget blocks
	for block_type, parentfield in WIDGET_PARENTFIELD.items():
		if block_type == "card":
			_remove_hidden_cards(doc, hidden)
			continue
		kept = [row for row in doc.get(parentfield) if f"{block_type}:{row.label}" not in hidden]
		doc.set(parentfield, kept)

	# apply label overrides to the surviving child rows
	for block_type, parentfield in WIDGET_PARENTFIELD.items():
		for row in doc.get(parentfield):
			override = overrides.get(f"{block_type}:{row.label}")
			if override and override.get("label"):
				row.label = override["label"]

	# add the item rows backing site-added blocks
	for entry in added:
		block = entry.get("block")
		item = entry.get("item")
		if block and item:
			_append_item(doc, block.get("type"), item)


def _remove_hidden_cards(doc, hidden: set[str]) -> None:
	"""Drop a hidden card's `Card Break` row and the `Link` rows that belong to it."""
	links = doc.get("links")
	kept = []
	skip_until_next_break = False
	for row in links:
		if row.type == "Card Break":
			skip_until_next_break = f"card:{row.label}" in hidden
		if skip_until_next_break:
			continue
		kept.append(row)
	doc.set("links", kept)


def _append_item(doc, block_type: str, item: dict) -> None:
	parentfield = WIDGET_PARENTFIELD.get(block_type)
	if not parentfield:
		return
	if block_type == "card":
		# a card item carries its own links; reuse the existing builder
		doc.build_links_table_from_card([item])
		return
	doc.append(parentfield, {k: v for k, v in item.items() if k != "doctype"})


def diff_customization(base_doc, edited_content: list, new_widgets: dict) -> dict:
	"""Derive the content delta of an edited workspace against its live base.

	`edited_content` is the full block list the editor submitted; `new_widgets` is the
	editor's payload of freshly-added item definitions keyed by widget type. Returns the
	`content_delta` dict stored on the customization.
	"""
	base_content = loads(base_doc.content or "[]")
	base_keys = [block_key(b) for b in base_content]
	base_map = dict(zip(base_keys, base_content, strict=False))
	base_set = set(base_keys)

	edited_keys = [block_key(b) for b in edited_content]
	edited_map = dict(zip(edited_keys, edited_content, strict=False))

	# freshly-added item definitions, indexed by (type, label) for added_blocks resolution
	item_index = {}
	for block_type in WIDGET_PARENTFIELD:
		for widget in new_widgets.get(block_type) or []:
			item_index[(block_type, widget.get("label"))] = widget

	hidden_blocks = [key for key in base_keys if key not in edited_map]

	added_blocks = []
	for key in edited_keys:
		if key in base_set:
			continue
		block = edited_map[key]
		block_type = block.get("type")
		label = (block.get("data") or {}).get(f"{block_type}_name")
		added_blocks.append({"block": block, "item": item_index.get((block_type, label))})

	block_overrides = {}
	for key in base_set & set(edited_keys):
		base_data = base_map[key].get("data") or {}
		edited_data = edited_map[key].get("data") or {}
		changed = {f: v for f, v in edited_data.items() if base_data.get(f) != v}
		if changed:
			block_overrides[key] = changed

	# store the edited order of shared blocks only when it diverges from the base order
	shared_edited = [key for key in edited_keys if key in base_set]
	shared_base = [key for key in base_keys if key in edited_map]
	block_order = edited_keys if shared_edited != shared_base else []

	return {
		"hidden_blocks": hidden_blocks,
		"block_order": block_order,
		"block_overrides": block_overrides,
		"added_blocks": added_blocks,
	}


def upsert_content_customization(workspace: str, edited_content: list, new_widgets: dict) -> None:
	"""Persist a content edit to a standard workspace as a delta (never touches the base)."""
	base_doc = frappe.get_cached_doc("Workspace", workspace)
	delta = diff_customization(base_doc, edited_content, new_widgets)
	customization = _get_or_new(workspace)
	customization.content_delta = dumps(delta)
	customization.save(ignore_permissions=True)


def upsert_property_customization(
	workspace: str,
	*,
	icon: str | None = None,
	indicator_color: str | None = None,
	visibility: str | None = None,
	override_sequence: bool | None = None,
	sequence_id: float | None = None,
) -> None:
	"""Persist visibility / appearance overrides to a standard workspace as a delta."""
	customization = _get_or_new(workspace)
	if icon is not None:
		customization.icon = icon
	if indicator_color is not None:
		customization.indicator_color = indicator_color
	if visibility is not None:
		customization.visibility = visibility
	if override_sequence is not None:
		customization.override_sequence = override_sequence
	if sequence_id is not None:
		customization.sequence_id = sequence_id
	customization.save(ignore_permissions=True)


def _get_or_new(workspace: str) -> "WorkspaceCustomization":
	if frappe.db.exists("Workspace Customization", workspace):
		return frappe.get_doc("Workspace Customization", workspace)
	return frappe.get_doc({"doctype": "Workspace Customization", "workspace": workspace})


@frappe.whitelist()
def reset_workspace_customization(workspace: str) -> None:
	"""Delete the customization, restoring the pristine app-owned workspace."""
	from frappe.desk.doctype.workspace.workspace import is_workspace_manager

	if not is_workspace_manager():
		frappe.throw(_("You need to be Workspace Manager to reset a workspace."), frappe.PermissionError)

	frappe.delete_doc_if_exists("Workspace Customization", workspace)
