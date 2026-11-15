# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document

# Cache key for the set of workspaces that have a customization, so the hot render
# path can skip a DB hit for the (vast) majority of uncustomized workspaces.
CUSTOMIZED_NAMES_CACHE_KEY = "customized_workspace_names"


class CustomWorkspace(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.has_role.has_role import HasRole
		from frappe.types import DF

		added_roles: DF.Table[HasRole]
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
		renderer: DF.Literal["Inherit", "Frappe UI"]
		sequence_id: DF.Float
		visibility: DF.Literal["Inherit", "Visible", "Hidden"]
		workspace: DF.Link
	# end: auto-generated types

	def autoname(self):
		# named after its workspace, which is how every reader finds it
		self.name = self.workspace

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
	layer on the live base, so the app's role changes flow through. The site's block edits are
	a Workspace Layout.
	"""
	_apply_roles(doc, customization)
	_apply_properties(doc, customization)


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


# A site's overrides of an app's page, each with the value that means "the app's own".
OVERRIDES = {"icon": None, "indicator_color": None, "visibility": "Inherit", "override_sequence": 0}


@frappe.whitelist(methods=["POST"])
def reset_page_fields(workspace: str, fields: list[str] | None = None) -> None:
	"""Bring back the app's value of each of `fields`, or of every override when none are named.
	`roles` names the role changes. A site's move to Frappe UI stays: it goes one way."""
	from frappe.desk.doctype.workspace.workspace import is_workspace_manager

	if not is_workspace_manager():
		frappe.throw(_("You need to be Workspace Manager to reset a workspace."), frappe.PermissionError)
	if not frappe.db.exists("Custom Workspace", workspace):
		return

	customization = frappe.get_doc("Custom Workspace", workspace)
	fields = frappe.parse_json(fields) or [*OVERRIDES, "roles"]
	for field in fields:
		if field == "roles":
			customization.set("added_roles", [])
			customization.set("removed_roles", [])
		elif field in OVERRIDES:
			customization.set(field, OVERRIDES[field])
	customization.save(ignore_permissions=True)


def overridden_fields(customization) -> list[str]:
	"""The page fields a site has changed from the app's."""
	changed = [
		field for field, default in OVERRIDES.items() if (customization.get(field) or default) != default
	]
	if customization.added_roles or customization.removed_roles:
		changed.append("roles")
	return changed
