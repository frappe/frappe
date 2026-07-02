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
		content: DF.LongText | None
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
		widgets: DF.LongText | None
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
		super().clear_cache()
		# the customization changes a *public* workspace, so bust the shared bootinfo
		# cache the same way Workspace.clear_cache does for public pages.
		frappe.cache.delete_key("bootinfo")
		frappe.cache.delete_value(CUSTOMIZED_NAMES_CACHE_KEY)


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

	The standard record stays the live base and is never written. Roles and visibility
	layer on the live base (app role changes flow through); content is shown from the
	site's saved snapshot.
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


def _apply_content(doc, customization) -> None:
	"""Show the site's saved block layout verbatim, plus the items backing added blocks.

	Content is a snapshot, not a delta: the site's arrangement is authoritative (the base
	is never written), so app changes to this workspace's layout do not flow through once
	it has been customized. Roles / visibility still layer on the live base.
	"""
	if customization.content:
		doc.content = customization.content

	# the layout's blocks are pointers; base widgets resolve from the base child tables, but
	# blocks the site added need their item definitions appended so they can be rendered.
	widgets = loads(customization.widgets or "{}")
	if widgets:
		_append_widgets(doc, widgets)


def _append_widgets(doc, widgets: dict) -> None:
	"""Append the stored added-widget item rows to a Workspace doc (mirrors save_new_widget)."""
	from frappe.desk.desktop import new_widget

	if widgets.get("chart"):
		doc.charts.extend(new_widget(widgets["chart"], "Workspace Chart", "charts"))
	if widgets.get("shortcut"):
		doc.shortcuts.extend(new_widget(widgets["shortcut"], "Workspace Shortcut", "shortcuts"))
	if widgets.get("quick_list"):
		doc.quick_lists.extend(new_widget(widgets["quick_list"], "Workspace Quick List", "quick_lists"))
	if widgets.get("custom_block"):
		doc.custom_blocks.extend(
			new_widget(widgets["custom_block"], "Workspace Custom Block", "custom_blocks")
		)
	if widgets.get("number_card"):
		doc.number_cards.extend(new_widget(widgets["number_card"], "Workspace Number Card", "number_cards"))
	if widgets.get("card"):
		doc.build_links_table_from_card(widgets["card"])


def upsert_content_customization(workspace: str, edited_content: list, new_widgets: dict) -> None:
	"""Persist a content edit to a standard workspace as a snapshot (never touches the base)."""
	customization = _get_or_new(workspace)

	# accumulate added-widget definitions across edit sessions (a later save only reports the
	# widgets added in *that* session), then keep only those still referenced by the layout.
	widgets = loads(customization.widgets or "{}")
	for widget_type, items in (new_widgets or {}).items():
		if items:
			widgets.setdefault(widget_type, []).extend(items)
	widgets = _prune_widgets(widgets, edited_content)

	customization.content = dumps(edited_content)
	customization.widgets = dumps(widgets)
	customization.save(ignore_permissions=True)


def _prune_widgets(widgets: dict, content: list) -> dict:
	"""Drop stored widget defs no longer referenced by the layout; dedupe by label."""
	referenced = {}
	for block in content:
		block_type = block.get("type")
		if block_type in WIDGET_PARENTFIELD:
			name = (block.get("data") or {}).get(f"{block_type}_name")
			referenced.setdefault(block_type, set()).add(name)

	pruned = {}
	for widget_type, items in widgets.items():
		kept = {}
		for item in items:
			if item.get("label") in referenced.get(widget_type, set()):
				kept[item.get("label")] = item
		if kept:
			pruned[widget_type] = list(kept.values())
	return pruned


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


def upsert_settings_customization(
	workspace: str,
	*,
	icon: str | None = None,
	indicator_color: str | None = None,
	roles: list[str] | None = None,
) -> None:
	"""Persist appearance + role gating for a standard workspace as a delta.

	Roles are stored as the diff against the live base (`added_roles` / `removed_roles`) so
	app changes to the base roles keep flowing through, matching `effective_roles`.
	"""
	customization = _get_or_new(workspace)
	if icon is not None:
		customization.icon = icon
	if indicator_color is not None:
		customization.indicator_color = indicator_color
	if roles is not None:
		base = {r.role for r in frappe.get_cached_doc("Workspace", workspace).roles}
		desired = set(roles)
		customization.set("added_roles", [{"role": r} for r in sorted(desired - base)])
		customization.set("removed_roles", [{"role": r} for r in sorted(base - desired)])
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
