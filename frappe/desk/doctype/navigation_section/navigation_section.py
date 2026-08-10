# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.desk.doctype.navigation_item.navigation_item import BUILT_IN_TYPES
from frappe.desk.doctype.navigation_section.counts import view_counts
from frappe.desk.doctype.navigation_section.overlay import apply_overlay
from frappe.desk.doctype.navigation_section.scope import DEFAULT_APP, UNSET, Scope, scope_of
from frappe.desk.doctype.navigation_section.sidebar import build_sidebar, item_type
from frappe.desk.doctype.saved_view.permissions import (
	can_manage_shared,
	guard_mutation,
	guard_scopes,
	has_access,
	query_conditions,
)
from frappe.model.document import Document
from frappe.utils import sbool

VIEW_FIELDS = (
	"name",
	"label",
	"icon",
	"reference_doctype",
	"type",
	"user",
	"is_default",
	"filters",
	"order_by",
	"columns",
	"rows",
	"group_by_field",
	"column_field",
	"title_field",
	"kanban_columns",
	"kanban_fields",
)

ITEM_FIELDS = (
	"parent",
	"name",
	"type",
	"label",
	"icon",
	"view",
	"dt",
	"url",
	"new_tab",
	"overrides",
	"hidden",
	"idx",
)


class NavigationSection(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.navigation_item.navigation_item import NavigationItem
		from frappe.types import DF

		app: DF.Data
		hidden: DF.Check
		label: DF.Data
		overrides: DF.Link | None
		reference_doctype: DF.Link | None
		items: DF.Table[NavigationItem]
		sequence: DF.Int
		user: DF.Link | None
	# end: auto-generated types

	def validate(self):
		guard_mutation(self)
		self.validate_overlay_has_owner()
		self.validate_overlay_target()
		self.validate_items()

	def validate_items(self):
		"""Validate every row against the version it is replacing."""
		stored = self.stored_items()
		for item in self.items:
			item.validate_item(stored.get(item.name))

	def stored_items(self):
		previous = self.get_doc_before_save()
		return {item.name: item for item in previous.items} if previous else {}

	def on_trash(self):
		guard_scopes({self.user or ""})
		self.delete_overlays()

	def delete_overlays(self):
		"""A shared section takes every user's overlay of it with it."""
		if self.user:
			return

		for name in frappe.get_all("Navigation Section", filters={"overrides": self.name}, pluck="name"):
			frappe.delete_doc("Navigation Section", name, ignore_permissions=True)

	def validate_overlay_has_owner(self):
		if self.overrides and not self.user:
			frappe.throw(_("Only a personal section can override a shared section."), frappe.ValidationError)

	def validate_overlay_target(self):
		if not self.overrides:
			return

		target = frappe.db.get_value(
			"Navigation Section", self.overrides, ["user", "app", "reference_doctype"], as_dict=True
		)
		if not target:
			return
		if target.user:
			frappe.throw(_("A personal section cannot be overridden."), frappe.ValidationError)
		if scope_of(target) != scope_of(self):
			frappe.throw(_("An overlay must target a section in the same scope."), frappe.ValidationError)


@frappe.whitelist()
@frappe.read_only()
def get_sidebar(reference_doctype: str = "", app: str = DEFAULT_APP, for_everyone: bool = False):
	"""The ordered sections the session user sees for `reference_doctype` in `app`."""
	guard_read(reference_doctype)

	scope = Scope(app, reference_doctype)
	sections, placed = shared_sidebar(scope) if sbool(for_everyone) else resolved_sidebar(scope)
	sidebar = build_sidebar(sections, placed, readable_doctypes(sections), app_item_targets(sections))
	default_view, is_stored = (
		resolve_default_view(reference_doctype, sidebar) if reference_doctype else (None, False)
	)
	return {
		"sections": sidebar,
		"can_manage_shared": can_manage_shared(),
		"default_view": default_view,
		"default_view_is_stored": is_stored,
	}


def guard_read(reference_doctype: str):
	"""Refuse a read of a doctype's sidebar the caller cannot open the list of."""
	if reference_doctype:
		frappe.has_permission(reference_doctype, throw=True)


def resolve_default_view(reference_doctype: str, sidebar: list):
	"""The view the plain list route opens with, as `(view name, is stored)`."""
	on_sidebar = {
		str(item["view"]["name"]) for section in sidebar for item in section["items"] if item["view"]
	}

	source = frappe.db.get_value(
		"Saved View",
		{"reference_doctype": reference_doctype, "user": frappe.session.user, "is_default": 1},
		"source_view",
	)
	if source and str(source) in on_sidebar:
		return source, True

	for section in sidebar:
		if section["user"] or section["hidden"]:
			continue
		for item in section["items"]:
			if item["view"] and not item["hidden"]:
				return item["view"]["name"], False
	return None, False


def resolved_sidebar(scope: Scope):
	"""The session user's sections in `scope`, resolved through their overlay, and the views they hold."""
	shared = get_shared_sections(scope)
	overlays = get_overlays(scope)
	for section in shared:
		overlay = overlays.get(section["name"], {})
		section["items"] = apply_overlay(section["items"], overlay.get("rows", []))
		section["sequence"] = overlay.get("sequence") or section["sequence"]
		section["hidden"] = overlay.get("hidden") or 0

	sections = sorted(shared + get_personal_sections(scope), key=order_of)
	return sections, get_placed_views(sections)


def shared_sidebar(scope: Scope):
	"""The shared sections in `scope`, unresolved: what a manager arranging for everyone is about to write."""
	sections = sorted(get_shared_sections(scope), key=order_of)
	return sections, get_placed_views(sections)


def order_of(section):
	return (section["sequence"], section["creation"])


@frappe.whitelist()
@frappe.read_only()
def get_view_counts(reference_doctype: str = "", refresh: bool = False, app: str = DEFAULT_APP):
	"""The record count of every view on the session user's sidebar, in one call."""
	guard_read(reference_doctype)
	return view_counts(Scope(app, reference_doctype), sbool(refresh))


def get_shared_sections(scope: Scope):
	return get_sections({**scope.filters(), "user": UNSET})


def get_personal_sections(scope: Scope):
	return get_sections({**scope.filters(), "user": frappe.session.user, "overrides": UNSET})


def get_overlays(scope: Scope):
	"""The caller's delta for each shared section, keyed by the section it overrides."""
	overlays = frappe.get_all(
		"Navigation Section",
		filters={**scope.filters(), "user": frappe.session.user, "overrides": ("is", "set")},
		fields=["name", "overrides", "sequence", "hidden"],
	)
	if not overlays:
		return {}

	rows_by_parent = get_section_rows([overlay["name"] for overlay in overlays])
	return {
		overlay["overrides"]: {
			"rows": rows_by_parent.get(overlay["name"], []),
			"sequence": overlay["sequence"],
			"hidden": overlay["hidden"],
		}
		for overlay in overlays
	}


def get_sections(filters):
	sections = frappe.get_all(
		"Navigation Section",
		filters=filters,
		fields=["name", "label", "user", "sequence", "hidden", "creation"],
		order_by="sequence asc, creation asc",
	)
	if not sections:
		return []

	rows_by_parent = get_section_rows([section["name"] for section in sections])
	for section in sections:
		section["items"] = rows_by_parent.get(section["name"], [])

	return sections


def get_section_rows(parents):
	"""Every section's child rows in one query — a sidebar is a page-load path."""
	rows = frappe.get_all(
		"Navigation Item",
		filters={"parent": ("in", parents), "parenttype": "Navigation Section"},
		fields=list(ITEM_FIELDS),
		order_by="idx asc",
	)

	grouped = {}
	for row in rows:
		grouped.setdefault(row["parent"], []).append(row)
	return grouped


def readable_doctypes(sections):
	"""Which of the doctypes the sections point at the session user may open a list of."""
	names = {row["dt"] for section in sections for row in section["items"] if row.get("dt")}
	if not names:
		return set()

	existing = frappe.get_all("DocType", filters={"name": ("in", list(names))}, pluck="name")
	return {name for name in existing if frappe.has_permission(name, "read")}


def app_item_targets(sections):
	"""Where the rows of an app-added type lead, keyed by row name."""
	names = [
		row["name"]
		for section in sections
		for row in section["items"]
		if item_type(row) not in BUILT_IN_TYPES
	]
	if not names:
		return {}

	targets = {}
	for method in frappe.get_hooks("navigation_item_targets"):
		targets.update(frappe.get_attr(method)(names) or {})
	return targets


def get_placed_views(sections):
	"""The Saved Views the sections hold, keyed by name."""
	names = {row["view"] for section in sections for row in section["items"] if row.get("view")}
	if not names:
		return {}

	views = frappe.get_all(
		"Saved View",
		filters={"name": ("in", list(names))},
		fields=list(VIEW_FIELDS),
	)
	return {str(view["name"]): view for view in views}


def get_permission_query_conditions(user: str | None = None) -> str:
	return query_conditions("Navigation Section", user)


def has_permission(doc, ptype=None, user=None, **kwargs) -> bool:
	return has_access(doc, ptype, user)
