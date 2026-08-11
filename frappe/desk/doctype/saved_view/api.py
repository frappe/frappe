# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""The sidebar's write half: create a view, place it, move it, drop it."""

import frappe
from frappe import _
from frappe.desk.doctype.navigation_section.scope import DEFAULT_APP, UNSET, Scope
from frappe.desk.doctype.saved_view.permissions import can_manage_shared, guard_scopes
from frappe.desk.doctype.saved_view.placement import placed_names, unplaced_views, without_view
from frappe.utils import sbool

PERSONAL_SECTION_LABEL = "Personal"
SHARED_SECTION_LABEL = "Views"

ViewName = str | int

COPIED_FIELDS = (
	"type",
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

STATE_FIELDS = ("filters", "order_by", "columns", "rows")


def view_state(filters, order_by, columns, rows):
	return dict(zip(STATE_FIELDS, (filters, order_by, columns, rows), strict=True))


@frappe.whitelist()
def create_view(
	reference_doctype: str,
	label: str,
	icon: str | None = None,
	shared: bool = False,
	filters: str | None = None,
	order_by: str | None = None,
	columns: str | None = None,
	rows: str | None = None,
	app: str = DEFAULT_APP,
	section: str | None = None,
):
	"""A new view, placed where its visibility says it belongs."""
	frappe.has_permission(reference_doctype, throw=True)
	shared = sbool(shared)

	view = frappe.get_doc(
		{
			"doctype": "Saved View",
			"label": label,
			"icon": icon,
			"reference_doctype": reference_doctype,
			"type": "list",
			"user": "" if shared else frappe.session.user,
			**view_state(filters, order_by, columns, rows),
		}
	).insert()

	scope = Scope(app, reference_doctype)
	place(named_section(section, scope) or target_section(scope, shared), view.name)
	return view.name


@frappe.whitelist()
def save_view_state(
	view: ViewName,
	filters: str | None = None,
	order_by: str | None = None,
	columns: str | None = None,
	rows: str | None = None,
):
	"""Write the live list state back into an existing view."""
	saved_view = frappe.get_doc("Saved View", view)
	frappe.has_permission(saved_view.reference_doctype, throw=True)
	saved_view.update(view_state(filters, order_by, columns, rows))
	saved_view.save()
	return saved_view.name


@frappe.whitelist()
def duplicate_view(view: ViewName, app: str = DEFAULT_APP):
	"""A copy of a view, always personal."""
	source = get_readable_view(view)

	copy = frappe.get_doc(
		{
			"doctype": "Saved View",
			"label": _("{0} (copy)").format(source.label),
			"icon": source.icon,
			"reference_doctype": source.reference_doctype,
			"user": frappe.session.user,
			**{field: source.get(field) for field in COPIED_FIELDS},
		}
	).insert()

	place(target_section(Scope(app, source.reference_doctype), shared=False), copy.name)
	return copy.name


@frappe.whitelist()
def set_as_default(view: ViewName):
	"""Copy a view's payload into the caller's default record, leaving the source alone."""
	source = get_readable_view(view)

	default = get_default_view(source.reference_doctype) or frappe.new_doc("Saved View")
	default.update(
		{
			"label": source.label,
			"icon": source.icon,
			"reference_doctype": source.reference_doctype,
			"user": frappe.session.user,
			"is_default": 1,
			"source_view": source.name,
			**{field: source.get(field) for field in COPIED_FIELDS},
		}
	)
	default.save()
	return default.name


@frappe.whitelist()
def add_to_sidebar(view: ViewName, app: str = DEFAULT_APP):
	"""Put a pool view back on the sidebar, in the section its visibility implies."""
	saved_view = get_readable_view(view)
	scope = Scope(app, saved_view.reference_doctype)
	place(target_section(scope, shared=not saved_view.user), saved_view.name)
	return saved_view.name


@frappe.whitelist()
def remove_from_sidebar(view: ViewName):
	"""Unplace, not delete — the view drops back to the pool and the + menu offers it."""
	saved_view = get_readable_view(view)
	guard_scopes({saved_view.user or ""}, "Saved View")
	unplace(saved_view.name)
	return saved_view.name


@frappe.whitelist()
def delete_view(view: ViewName):
	saved_view = get_readable_view(view)
	guard_scopes({saved_view.user or ""}, "Saved View")
	unplace(saved_view.name)
	frappe.delete_doc("Saved View", saved_view.name)
	return saved_view.name


@frappe.whitelist()
def move_view(view: ViewName, shared: bool, app: str = DEFAULT_APP):
	"""Move a view across the shared/personal boundary, which is what flips its visibility."""
	shared = sbool(shared)
	saved_view = get_readable_view(view)

	guard_scopes({saved_view.user or "", "" if shared else frappe.session.user}, "Saved View")

	saved_view.user = "" if shared else frappe.session.user
	saved_view.is_default = 0
	saved_view.save()

	unplace(saved_view.name)
	place(target_section(Scope(app, saved_view.reference_doctype), shared), saved_view.name)
	return saved_view.name


@frappe.whitelist()
@frappe.read_only()
def get_pool(reference_doctype: str, app: str = DEFAULT_APP):
	"""The saved views no section holds that the caller could place — what the + menu adds back."""
	frappe.has_permission(reference_doctype, throw=True)

	filters = {"reference_doctype": reference_doctype, "is_default": 0}
	if not can_manage_shared("Saved View"):
		filters["user"] = frappe.session.user

	views = frappe.get_all(
		"Saved View",
		filters=filters,
		fields=["name", "label", "icon", "user"],
		order_by="modified desc",
	)
	return unplaced_views(views, placed_names(visible_sections(Scope(app, reference_doctype))))


def named_section(name: str | None, scope: Scope):
	"""The section the caller asked for, or `None` to fall back to where the view's visibility puts it."""
	if not name:
		return None

	section = frappe.get_doc("Navigation Section", name)
	if (section.app, section.reference_doctype or "") != (scope.app, scope.reference_doctype):
		frappe.throw(_("That section belongs to another sidebar."))

	if not frappe.has_permission("Navigation Section", "write", doc=section):
		return None
	return section


def target_section(scope: Scope, shared: bool):
	"""The section a view lands in, created on first use."""
	if shared:
		guard_scopes({""}, "Navigation Section")
		return get_or_create_section(scope, SHARED_SECTION_LABEL, user="")

	return get_or_create_section(scope, PERSONAL_SECTION_LABEL, user=frappe.session.user)


def get_or_create_section(scope: Scope, label: str, user: str):
	"""The section matching `label` and `scope`, created when there is none."""
	filters = {
		**scope.filters(),
		"label": label,
		"overrides": UNSET,
		"user": user or UNSET,
	}

	name = frappe.db.get_value("Navigation Section", filters, "name", order_by="creation asc")
	if name:
		return frappe.get_doc("Navigation Section", name)

	return frappe.get_doc(
		{
			"doctype": "Navigation Section",
			"label": label,
			**scope.as_fields(),
			"user": user,
		}
	).insert()


def place(section, view):
	if str(view) in {str(row.view) for row in section.items}:
		return

	section.append("items", {"type": "view", "view": view})
	section.save()


def unplace(view):
	"""Clear a view out of every section it sits in, including ones the caller cannot otherwise write."""
	for parent in frappe.get_all(
		"Navigation Item",
		filters={"view": view, "parenttype": "Navigation Section"},
		pluck="parent",
		distinct=True,
	):
		section = frappe.get_doc("Navigation Section", parent)
		section.items = without_view(section.items, view)
		section.save(ignore_permissions=True)


def visible_sections(scope: Scope):
	from frappe.desk.doctype.navigation_section.navigation_section import (
		get_personal_sections,
		get_shared_sections,
	)

	return get_shared_sections(scope) + get_personal_sections(scope)


@frappe.whitelist()
@frappe.read_only()
def get_landing_view(reference_doctype: str):
	"""The per-user default the list opens with when the URL names no view."""
	frappe.has_permission(reference_doctype, throw=True)

	default = get_default_view(reference_doctype)
	if not default:
		return None
	return {field: default.get(field) for field in ("name", "label", "icon", "type", *STATE_FIELDS)}


@frappe.whitelist()
def save_landing_state(
	reference_doctype: str,
	filters: str | None = None,
	order_by: str | None = None,
	columns: str | None = None,
	rows: str | None = None,
):
	"""Auto-save the landing list's tweaks into the caller's own default."""
	frappe.has_permission(reference_doctype, throw=True)

	default = get_default_view(reference_doctype) or frappe.get_doc(
		{
			"doctype": "Saved View",
			"label": _("Default"),
			"reference_doctype": reference_doctype,
			"type": "list",
			"user": frappe.session.user,
			"is_default": 1,
		}
	)
	default.update(view_state(filters, order_by, columns, rows))
	default.save()
	return default.name


def get_default_view(reference_doctype: str):
	name = frappe.db.get_value(
		"Saved View",
		{"reference_doctype": reference_doctype, "user": frappe.session.user, "is_default": 1},
		"name",
	)
	return frappe.get_doc("Saved View", name) if name else None


def get_readable_view(view: ViewName):
	saved_view = frappe.get_doc("Saved View", view)
	if saved_view.user and saved_view.user != frappe.session.user and not can_manage_shared("Saved View"):
		frappe.throw(_("You can only change your own views."), frappe.PermissionError)
	return saved_view
