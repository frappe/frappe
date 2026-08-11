# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Arranging the sidebar: the order of items and sections, and which of them a user has hidden."""

import frappe
from frappe import _
from frappe.desk.doctype.navigation_item.navigation_item import VIEW
from frappe.desk.doctype.navigation_section.navigation_section import guard_read
from frappe.desk.doctype.navigation_section.overlay import apply_overlay
from frappe.desk.doctype.navigation_section.scope import DEFAULT_APP, Scope, scope_of
from frappe.desk.doctype.navigation_section.sidebar import item_type
from frappe.desk.doctype.saved_view.api import ViewName, get_readable_view, unplace
from frappe.desk.doctype.saved_view.permissions import guard_scopes
from frappe.utils import sbool

JsonList = str | list
JsonDict = str | dict

UNSETTABLE_FIELDS = frozenset(
	{"name", "idx", "parent", "parentfield", "parenttype", "owner", "overrides", "hidden", "view"}
)


@frappe.whitelist()
def arrange_items(section: str, items: JsonList, for_everyone: bool = False):
	"""Set the order and hidden flags of one section, and return the record written."""
	target = get_writable_section(section)
	overlay = own_overlay(target)
	rows = frappe.parse_json(items)
	validate_same_membership(target, overlay, rows)

	if target.user or sbool(for_everyone):
		shared = {row.name for row in target.items}
		reorder_rows(target, [row for row in rows if str(row.get("name")) in shared])
		if not target.user:
			drop_overlay(target, rows)
		return target.name

	return write_overlay_rows(get_or_create_overlay(target), rows).name


@frappe.whitelist()
def add_item(section: str, item: JsonDict, for_everyone: bool = False):
	"""Add a navigation item to `section` and return the new row's name."""
	fields = settable_fields(frappe.parse_json(item))
	if fields.get("type", VIEW) == VIEW:
		frappe.throw(_("A view is placed on the sidebar, not added to a section."), frappe.ValidationError)

	holder = destination(section, for_everyone)
	row = holder.append("items", fields)
	holder.save()
	return row.name


@frappe.whitelist()
def remove_item(section: str, item: str):
	"""Drop one row from a section."""
	holder = locate_row(section, item)[0]
	holder.items = [row for row in holder.items if row.name != item]
	holder.save()


@frappe.whitelist()
def get_item(section: str, item: str):
	"""What one row currently holds, for an editor opening a form over it."""
	return settable_fields(locate_row(section, item)[1].as_dict())


@frappe.whitelist()
def update_item(
	section: str,
	item: str,
	label: str,
	icon: str = "",
	for_everyone: bool = False,
	values: JsonDict | None = None,
):
	"""Rename one row, set its icon, and — where the caller may — change where it leads."""
	target = get_writable_section(section)
	if target.overrides:
		frappe.throw(_("An overlay is written through the section it deltas."), frappe.ValidationError)

	fields = settable_fields(frappe.parse_json(values)) if values else {}
	fields.pop("type", None)

	overlay = own_overlay(target)
	own = find_own_row(overlay, item)
	if own:
		own.update({**fields, "label": require_label(label), "icon": (icon or "").strip()})
		overlay.save()
		return

	row = get_row(target, item)
	if item_type(row.as_dict()) == VIEW:
		frappe.throw(_("A view is renamed on the view itself, not on its row."), frappe.ValidationError)

	naming = {"label": require_label(label), "icon": (icon or "").strip()}
	if target.user or sbool(for_everyone):
		row.update({**fields, **naming})
		target.save()
		if not target.user:
			clear_override(target, item)
		return

	if fields:
		frappe.throw(
			_("Where a shared item leads is the same for everybody. Change it for everyone, or hide it."),
			frappe.PermissionError,
		)

	write_override(target, item, naming)


def require_label(label: str) -> str:
	named = (label or "").strip()
	if not named:
		frappe.throw(_("An item needs a label."), frappe.ValidationError)
	return named


def write_override(section, item: str, naming: dict):
	"""The caller's own name for a shared row, on their overlay."""
	overlay = materialized_overlay(section)
	find_overlay_row(overlay, item).update(differing(naming, get_row(section, item)))
	overlay.save()


def materialized_overlay(section):
	"""The caller's overlay of `section`, carrying the arrangement they currently see."""
	overlay = get_or_create_overlay(section)
	seen = apply_overlay(as_dicts(section.items), as_dicts(overlay.items))
	return write_overlay_rows(overlay, [{"name": row["name"], "hidden": row["hidden"]} for row in seen])


def own_overlay(section):
	"""The caller's overlay of `section` as a document, or None for a personal section."""
	if section.user:
		return None
	name = find_overlay(section)
	return frappe.get_doc("Navigation Section", name) if name else None


def find_own_row(overlay, item: str):
	"""One of the caller's own items on their overlay: a row naming no shared row."""
	if not overlay:
		return None
	for row in overlay.items:
		if not row.overrides and row.name == item:
			return row


def locate_row(section: str, item: str):
	"""The record holding the named row and the row itself: the caller's overlay, else the section."""
	target = get_writable_section(section)
	overlay = own_overlay(target)
	own = find_own_row(overlay, item)
	return (overlay, own) if own else (target, get_row(target, item))


def differing(naming: dict, shared) -> dict:
	"""The naming, minus whatever the shared row already says."""
	return {field: "" if value == (shared.get(field) or "") else value for field, value in naming.items()}


def as_dicts(rows):
	"""Overlay rows as the plain dicts `apply_overlay` reads."""
	return [row.as_dict() for row in rows]


def clear_override(section, item: str):
	"""Drop the caller's own name for a row they have just renamed for everybody."""
	name = find_overlay(section)
	if not name:
		return

	overlay = frappe.get_doc("Navigation Section", name)
	row = find_overlay_row(overlay, item)
	if not row or not (row.label or row.icon):
		return

	row.update({"label": "", "icon": ""})
	overlay.save()


def find_overlay_row(overlay, item: str):
	for row in overlay.items:
		if row.overrides == item:
			return row


def get_row(section, item: str):
	for row in section.items:
		if row.name == item:
			return row
	frappe.throw(_("That item is not in this section."), frappe.ValidationError)


def settable_fields(item: dict) -> dict:
	"""The payload narrowed to fields a Navigation Item has and a caller may set."""
	fields = {field.fieldname for field in frappe.get_meta("Navigation Item").fields}
	return {key: value for key, value in item.items() if key in fields - UNSETTABLE_FIELDS}


@frappe.whitelist()
def hide_section(section: str, hidden: bool = True):
	"""Take one section off the caller's own sidebar, or put it back."""
	target = get_writable_section(section)
	flag = 1 if sbool(hidden) else 0

	if target.user:
		target.hidden = flag
		return target.save().name

	overlay = get_or_create_overlay(target)
	overlay.hidden = flag
	return overlay.save().name


@frappe.whitelist()
def move_item_to_section(
	source: str, item: str, section: str, index: int | None = None, for_everyone: bool = False
):
	"""Drag an item that holds no view out of `source` and into `section` at `index`."""
	origin, row = locate_row(source, item)
	if item_type(row.as_dict()) == VIEW:
		frappe.throw(_("A view is moved by its placement, not as a row."), frappe.ValidationError)

	carried = {**settable_fields(row.as_dict()), "hidden": 1 if row.hidden else 0}
	origin.items = [kept for kept in origin.items if kept.name != item]
	origin.save()

	target = destination(section, for_everyone)
	position = len(target.items) if index is None else max(0, min(int(index), len(target.items)))
	moved = target.append("items", carried, position=position)
	target.save()
	return moved.name


def destination(section: str, for_everyone: bool):
	"""The record a move or an add writes into: the section, or the caller's overlay of it."""
	target = get_writable_section(section)
	if target.overrides:
		frappe.throw(_("An item is placed through the section an overlay deltas."), frappe.ValidationError)
	if target.user or sbool(for_everyone):
		return target
	return materialized_overlay(target)


@frappe.whitelist()
def move_view_to_section(view: ViewName, section: str, index: int | None = None):
	"""Drag a view out of whatever section holds it and into `section` at `index`."""
	target = get_writable_section(section)
	if target.overrides:
		frappe.throw(_("A view cannot be placed into an overlay."), frappe.ValidationError)

	saved_view = get_readable_view(view)
	shared = not target.user
	guard_scopes({saved_view.user or "", "" if shared else frappe.session.user}, "Saved View")

	if bool(saved_view.user) == shared:
		saved_view.user = "" if shared else frappe.session.user
		saved_view.is_default = 0
		saved_view.save()

	unplace(saved_view.name)
	target.reload()
	insert_at(target, saved_view.name, index)
	return saved_view.name


@frappe.whitelist()
def create_section(label: str, reference_doctype: str = "", shared: bool = False, app: str = DEFAULT_APP):
	"""A new, empty section at the bottom of the sidebar."""
	guard_read(reference_doctype)
	shared = sbool(shared)
	scope = Scope(app, reference_doctype)

	section = frappe.get_doc(
		{
			"doctype": "Navigation Section",
			"label": label,
			**scope.as_fields(),
			"user": "" if shared else frappe.session.user,
			"sequence": next_sequence(scope),
		}
	).insert()
	return section.name


@frappe.whitelist()
def arrange_sections(
	sections: JsonList, reference_doctype: str = "", for_everyone: bool = False, app: str = DEFAULT_APP
):
	"""Reorder sections; `for_everyone` writes the shared records, anything else the caller's overlay."""
	guard_read(reference_doctype)
	for_everyone = sbool(for_everyone)
	if for_everyone:
		guard_scopes({""}, "Navigation Section")

	scope = Scope(app, reference_doctype)
	for sequence, name in enumerate(frappe.parse_json(sections), start=1):
		section = frappe.get_doc("Navigation Section", name)
		if scope_of(section) != scope:
			frappe.throw(_("That section belongs to another sidebar."), frappe.ValidationError)
		if section.user:
			place_section(section, sequence)
		elif for_everyone:
			place_section(section, sequence)
			reset_overlay_sequence(section)
		else:
			place_overlay_sequence(section, sequence)


def get_writable_section(section: str):
	target = frappe.get_doc("Navigation Section", section)
	if target.user and target.user != frappe.session.user:
		frappe.throw(_("You can only change your own views."), frappe.PermissionError)
	return target


def validate_same_membership(section, overlay, rows):
	"""Refuse an arrangement whose row list gained or lost an item."""
	known = {row.name for row in section.items}
	if overlay:
		known |= {row.name for row in overlay.items if not row.overrides}

	if {str(row.get("name")) for row in rows} != known:
		frappe.throw(_("This section has changed. Reload and try again."), frappe.ValidationError)


def reorder_rows(section, rows):
	"""The section's own rows, repositioned and reflagged in place."""
	arrangement = {
		str(row.get("name")): (index, 1 if row.get("hidden") else 0)
		for index, row in enumerate(rows, start=1)
	}
	for item in section.items:
		item.idx, item.hidden = arrangement[item.name]

	section.items.sort(key=lambda item: item.idx)
	return section.save()


def write_overlay_rows(overlay, rows):
	"""The caller's arrangement of a shared section: a delta per shared row, plus their own items."""
	own = {row.name: row for row in overlay.items if not row.overrides}
	named = {row.overrides: {"label": row.label, "icon": row.icon} for row in overlay.items if row.overrides}

	arranged = []
	for index, row in enumerate(rows, start=1):
		name = str(row.get("name"))
		hidden = 1 if row.get("hidden") else 0
		if name in own:
			own[name].update({"idx": index, "hidden": hidden})
			arranged.append(own[name])
		else:
			arranged.append({"overrides": name, "hidden": hidden, **named.get(name, {})})

	overlay.items = []
	for row in arranged:
		overlay.append("items", row)
	return overlay.save()


def insert_at(section, view, index):
	"""Place a view row at `index`, shifting the rows below it down."""
	position = len(section.items) if index is None else max(0, min(int(index), len(section.items)))
	section.append("items", {"type": "view", "view": view}, position=position)
	section.save()


def place_section(section, sequence):
	if section.sequence != sequence:
		section.sequence = sequence
		section.save()


def place_overlay_sequence(section, sequence):
	"""Where the caller put a shared section, written as their overlay's `sequence`."""
	if effective_sequence(section) == sequence:
		return
	overlay = get_or_create_overlay(section)
	overlay.sequence = sequence
	overlay.save()


def effective_sequence(section):
	"""The position the caller currently sees a shared section at."""
	overlay = find_overlay(section)
	overlay_sequence = frappe.db.get_value("Navigation Section", overlay, "sequence") if overlay else 0
	return overlay_sequence or section.sequence


def reset_overlay_sequence(section):
	name = find_overlay(section)
	if name and frappe.db.get_value("Navigation Section", name, "sequence"):
		frappe.db.set_value("Navigation Section", name, "sequence", 0)


def find_overlay(section):
	"""The caller's delta record for a shared section, if they have ever rearranged it."""
	return frappe.db.get_value(
		"Navigation Section", {"overrides": section.name, "user": frappe.session.user}, "name"
	)


def get_or_create_overlay(section):
	name = find_overlay(section)
	if name:
		return frappe.get_doc("Navigation Section", name)

	return frappe.get_doc(
		{
			"doctype": "Navigation Section",
			"label": section.label,
			**scope_of(section).as_fields(),
			"user": frappe.session.user,
			"overrides": section.name,
		}
	).insert()


def drop_overlay(section, rows):
	"""Drop the caller's row deltas for a section whose order they have just published."""
	name = find_overlay(section)
	if not name:
		return

	overlay = frappe.get_doc("Navigation Section", name)
	if any(not row.overrides for row in overlay.items):
		return write_overlay_rows(overlay, rows)

	if not (overlay.sequence or overlay.hidden):
		return frappe.delete_doc("Navigation Section", name)

	overlay.items = []
	overlay.save()


def next_sequence(scope: Scope):
	"""Past every section the caller can see, shared or their own."""
	filters = {**scope.filters(), "user": ("in", ("", None, frappe.session.user))}
	highest = frappe.db.get_value("Navigation Section", filters, "sequence", order_by="sequence desc")
	return (highest or 0) + 1
