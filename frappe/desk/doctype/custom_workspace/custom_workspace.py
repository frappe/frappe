# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from json import dumps, loads

import frappe
from frappe import _
from frappe.desk.doctype.workspace_variant.workspace_variant import (
	DEFAULT_LAYOUT,
	sanitize_variants,
	validate_variants,
)
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

# what `build_links_table_from_card` reads from a stored card's links
CARD_LINK_KEYS = (
	"label",
	"link_type",
	"link_to",
	"onboard",
	"only_for",
	"dependencies",
	"is_query_report",
)

# Cache key for the set of workspaces that have a customization, so the hot render
# path can skip a DB hit for the (vast) majority of uncustomized workspaces.
CUSTOMIZED_NAMES_CACHE_KEY = "customized_workspace_names"


class CustomWorkspace(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.has_role.has_role import HasRole
		from frappe.desk.doctype.workspace_variant.workspace_variant import WorkspaceVariant
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
		renderer: DF.Literal["Inherit", "Legacy", "Frappe UI"]
		sequence_id: DF.Float
		variants: DF.Table[WorkspaceVariant]
		visibility: DF.Literal["Inherit", "Visible", "Hidden"]
		widgets: DF.LongText | None
		workspace: DF.Link
	# end: auto-generated types

	def before_validate(self):
		# The same trip through the XSS sanitizer the base document takes, for the same reason:
		# this row carries a workspace's blocks too.
		from frappe.desk.doctype.workspace.workspace import sanitize_content

		self.content = sanitize_content(self.content)
		self.widgets = sanitize_content(self.widgets)
		sanitize_variants(self.variants)

	def validate(self):
		if not frappe.db.get_value("Workspace", self.workspace, "standard"):
			frappe.throw(_("Only standard (app-shipped) workspaces can be customized."))
		validate_variants(self.variants)

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
		names = frappe.get_all("Custom Workspace", pluck="workspace")
		frappe.cache.set_value(CUSTOMIZED_NAMES_CACHE_KEY, names)
	return set(names)


def get_customization(workspace: str) -> "CustomWorkspace | None":
	"""Return the customization for a workspace, or None. Cheap when uncustomized."""
	if workspace not in get_customized_workspace_names():
		return None
	# customization name == workspace name (autoname: field:workspace)
	try:
		return frappe.get_cached_doc("Custom Workspace", workspace)
	except frappe.DoesNotExistError:
		frappe.clear_last_message()
		return None


def effective_roles(base_roles: list[str], customization: "CustomWorkspace") -> list[str]:
	"""(base.roles - removed_roles) | added_roles."""
	removed = {r.role for r in customization.removed_roles}
	roles = {r for r in base_roles if r not in removed}
	roles.update(r.role for r in customization.added_roles)
	return list(roles)


def effective_renderer(base_renderer: str, customization: "CustomWorkspace | None") -> str:
	"""The site's renderer unless it is Inherit, else the app's."""
	if customization and customization.renderer and customization.renderer != "Inherit":
		return customization.renderer
	return base_renderer


def apply_customization(doc, customization: "CustomWorkspace") -> None:
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
	doc.renderer = effective_renderer(doc.renderer, customization)
	if customization.indicator_color:
		doc.indicator_color = customization.indicator_color
	if customization.override_sequence:
		doc.sequence_id = customization.sequence_id


def _apply_content(doc, customization) -> None:
	"""Show the site's saved layouts verbatim.

	Each layout is a snapshot, not a delta: its blocks and its whole widget set. Customizing one
	freezes it against the app's later changes to that layout, and leaves every other layout
	tracking the app. Roles / visibility still layer on the live base.
	"""
	if customization.content:
		doc.content = customization.content
		replace_widgets(doc, loads(customization.widgets or "{}"))

	# a site row replaces the app's row for its role in place; the site's own come last
	site_rows = {row.role: row for row in customization.variants}
	rows = [site_rows.pop(row.role, row) for row in doc.variants]
	rows.extend(site_rows.values())
	doc.set("variants", [{"role": r.role, "content": r.content, "widgets": r.widgets} for r in rows])


def replace_widgets(doc, widgets: dict) -> None:
	"""Make a layout's widget rows exactly the stored set (a role layout's `widgets` is whole)."""
	from frappe.desk.desktop import new_widget

	for widget_type, parentfield in WIDGET_PARENTFIELD.items():
		if widget_type == "card":
			continue
		doctype = doc.meta.get_field(parentfield).options
		doc.set(parentfield, new_widget(widgets.get(widget_type), doctype, parentfield))
	doc.set("links", [])
	doc.build_links_table_from_card(widgets.get("card") or [])


def upsert_content_customization(
	workspace: str, edited_content: list, new_widgets: dict, variant: str | None = None
) -> None:
	"""Persist a layout edit to a standard workspace as a site snapshot (never touches the base).

	The first edit of a layout copies its whole widget set in, so the snapshot keeps every widget
	the app layout had. A later save only adds the widgets new in that session.
	"""
	customization = _get_or_new(workspace)
	base = frappe.get_cached_doc("Workspace", workspace)

	if variant and variant != DEFAULT_LAYOUT:
		row = next((r for r in customization.variants if r.role == variant), None)
		if row:
			widgets = loads(row.widgets or "{}")
		else:
			app_row = next((r for r in base.variants if r.role == variant), None)
			widgets = loads(app_row.widgets or "{}") if app_row else {}
			row = customization.append("variants", {"role": variant})
		row.content = dumps(edited_content)
		row.widgets = dumps(_prune_widgets(merge_widgets(widgets, new_widgets), edited_content))
	else:
		widgets = loads(customization.widgets or "{}") if customization.content else snapshot_widgets(base)
		customization.content = dumps(edited_content)
		customization.widgets = dumps(_prune_widgets(merge_widgets(widgets, new_widgets), edited_content))

	customization.save(ignore_permissions=True)


def merge_widgets(widgets: dict, new_widgets: dict | None) -> dict:
	"""The stored set plus a save's new widgets; a new one wins over a stored one of its label."""
	merged = {widget_type: list(items) for widget_type, items in widgets.items()}
	for widget_type, items in (new_widgets or {}).items():
		merged.setdefault(widget_type, []).extend(items or [])
	return merged


def snapshot_widgets(doc) -> dict:
	"""A Workspace's widget tables in the stored widgets shape."""
	widgets = {}
	for widget_type, parentfield in WIDGET_PARENTFIELD.items():
		if widget_type == "card":
			continue
		rows = [
			row.as_dict(no_default_fields=True, no_child_table_fields=True) for row in doc.get(parentfield)
		]
		if rows:
			widgets[widget_type] = rows

	cards = [
		{
			"label": card.label,
			"icon": card.icon,
			"description": card.description,
			"hidden": card.hidden,
			"links": dumps([{key: link.get(key) for key in CARD_LINK_KEYS} for link in card.links]),
		}
		for card in doc.get_link_groups()
		if card.links
	]
	if cards:
		widgets["card"] = cards
	return widgets


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
	renderer: str | None = None,
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
	if renderer is not None:
		customization.renderer = renderer
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


def _get_or_new(workspace: str) -> "CustomWorkspace":
	if frappe.db.exists("Custom Workspace", workspace):
		return frappe.get_doc("Custom Workspace", workspace)
	return frappe.get_doc({"doctype": "Custom Workspace", "workspace": workspace})


@frappe.whitelist()
def reset_workspace_customization(workspace: str, variant: str | None = None) -> None:
	"""Restore the app's workspace, or with `variant` only that layout (a role or the default)."""
	from frappe.desk.doctype.workspace.workspace import is_workspace_manager

	if not is_workspace_manager():
		frappe.throw(_("You need to be Workspace Manager to reset a workspace."), frappe.PermissionError)

	if not variant:
		frappe.delete_doc_if_exists("Custom Workspace", workspace)
		return

	if not frappe.db.exists("Custom Workspace", workspace):
		return
	customization = frappe.get_doc("Custom Workspace", workspace)
	if variant == DEFAULT_LAYOUT:
		customization.content = None
		customization.widgets = None
	else:
		base_roles = {row.role for row in frappe.get_cached_doc("Workspace", workspace).variants}
		if variant not in base_roles:
			frappe.throw(
				_("The {0} layout is this site's own, so there is no app layout to go back to.").format(
					_(variant)
				)
			)
		customization.set("variants", [row for row in customization.variants if row.role != variant])
	customization.save(ignore_permissions=True)
