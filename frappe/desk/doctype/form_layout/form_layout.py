# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import copy
import functools
import json
import re
from collections.abc import Callable

import frappe
from frappe import _
from frappe.desk.doctype.form_layout.app_layout import content_hash, read_app_layouts
from frappe.desk.form.linked_with import get_parent_doctypes
from frappe.model import child_table_fields, data_fieldtypes, default_fields, optional_fields
from frappe.model.document import Document
from frappe.model.meta import Meta

FORM_LAYOUT_TYPES = ("Details", "Side Panel", "Quick Entry", "New Record")
OMITTING_LAYOUT_TYPES = ("Details", "New Record")
CREATE_LAYOUT_TYPES = ("Quick Entry", "New Record")
CHILD_LAYOUT_TYPES = ("Details",)
SINGLE_LAYOUT_TYPES = ("Details", "Side Panel")
LAYOUT_BREAKS = ("Section Break", "Column Break", "Tab Break")
SECTION_ONLY_KEYS = ("collapsibleDependsOn",)
# A `write_layout_row` argument left at this keeps the row's stored value.
KEEP = object()
# Mirrors `DROPPED_FIELDTYPES` in `ui/src/components/FormLayout/buildLayoutFromMeta.ts`.
DROPPED_FIELDTYPES = (*LAYOUT_BREAKS, "Fold", "Attachment Gallery")
STANDARD_FIELDS = frozenset(default_fields + child_table_fields + optional_fields)


class FormLayout(Document):
	def validate(self):
		self.validate_app()
		self.validate_single_default()
		self.validate_layout()
		if self.flags.writes_omitted:
			self.omitted = frappe.as_json(omitted_fieldnames(self.dt, parse_layout(self.layout)))

	def validate_layout(self):
		self.name_layout()
		tabs = parse_layout(self.layout)
		self.validate_entries(tabs)
		self.validate_section_only_keys(tabs)
		self.validate_inline_fields(tabs)
		self.validate_names_are_not_fields(tabs)
		self.validate_omitted()

	def on_update(self):
		publish_doctype_update(self.dt)
		previous = self.get_doc_before_save()
		if previous and previous.dt != self.dt:
			publish_doctype_update(previous.dt)

	def on_trash(self):
		publish_doctype_update(self.dt)

	def validate_names_are_not_fields(self, tabs: list):
		"""Refuse a tab or section named like a data field; a script addresses both by one name."""
		if not tabs:
			return
		fieldnames = data_fieldnames(self.fields_meta()) | {
			field["fieldname"] for field in inline_fields(tabs)
		}
		for tab in tabs:
			refuse_field_name(_("Tab"), tab["name"], fieldnames, self.dt)
			for section in tab["sections"]:
				refuse_field_name(_("Section"), section["name"], fieldnames, self.dt)

	def fields_meta(self) -> Meta:
		"""The DocType editor checks a layout against the fields its save is about to write."""
		return self.flags.meta or frappe.get_meta(self.dt)

	def validate_omitted(self):
		"""Drop each new entry that names no field, with a message; old entries stay."""
		omitted = self.omitted_fields()
		previous = self.get_doc_before_save()
		kept = set(parse_omitted(previous.omitted)) if previous and previous.dt == self.dt else set()
		meta = frappe.get_meta(self.dt)
		allowed = [
			fieldname for fieldname in omitted if fieldname in kept or not refuse_omitted(fieldname, meta)
		]
		self.omitted = frappe.as_json(allowed) if allowed else None

	def omitted_fields(self) -> list[str]:
		try:
			omitted = json.loads(self.omitted) if self.omitted else []
		except (json.JSONDecodeError, TypeError) as e:
			frappe.throw(_("Omitted Fields is not valid JSON: {0}").format(str(e)), title=_("Invalid Layout"))
		if not isinstance(omitted, list) or not all(isinstance(entry, str) for entry in omitted):
			frappe.throw(_("Omitted Fields must be a list of fieldnames."), title=_("Invalid Layout"))
		return list(dict.fromkeys(omitted))

	def validate_entries(self, tabs: list):
		if any(not isinstance(entry, str | dict) for entry in layout_entries(tabs)):
			frappe.throw(
				_("A column holds fieldnames and fields the layout defines, nothing else."),
				title=_("Invalid Layout"),
			)

	def validate_section_only_keys(self, tabs: list):
		for tab in tabs:
			refuse_section_only_keys(_("Tab"), tab)
			for section in tab["sections"]:
				for column in section["columns"]:
					refuse_section_only_keys(_("Column"), column)

	def validate_inline_fields(self, tabs: list):
		fields = inline_fields(tabs)
		if not fields:
			return
		if self.type not in CREATE_LAYOUT_TYPES:
			frappe.throw(
				_("Only a Quick Entry or New Record layout can define a field of its own."),
				title=_("Invalid Layout"),
			)
		meta = self.fields_meta()
		for field in fields:
			validate_inline_field(field, meta)
		refuse_repeated_inline_fields(tabs, fields)

	def name_layout(self):
		"""Name every container at write time, so a label edit cannot rename what a script addresses."""
		if not self.layout:
			return
		tree = self.layout_tree()
		tree[:] = [node for node in tree if isinstance(node, dict)]
		as_authored = copy.deepcopy(tree)
		tabs = wrap_tabless(tree)
		name_layout_containers(tabs)
		validate_unique_names(tabs)
		if tree != as_authored:
			self.layout = frappe.as_json(tree)

	def layout_tree(self) -> list:
		"""The `layout` field parsed, refusing what `parse_layout` would quietly read as empty."""
		try:
			tree = json.loads(self.layout)
		except (json.JSONDecodeError, TypeError) as e:
			frappe.throw(_("Layout is not valid JSON: {0}").format(str(e)), title=_("Invalid Layout"))
		if not isinstance(tree, list):
			frappe.throw(_("Layout must be a list of containers."), title=_("Invalid Layout"))
		return tree

	def validate_app(self):
		self.app = (self.app or "").strip() or None
		if self.app and self.app not in frappe.get_installed_apps():
			frappe.throw(
				_("{0} is not an installed app.").format(frappe.bold(self.app)), title=_("Invalid App")
			)

	def validate_single_default(self):
		if self.condition:
			return
		default = frappe.get_all(
			"Form Layout",
			filters={
				**default_filters(self.dt, self.type, self.app),
				"name": ("!=", self.name or ""),
			},
			limit=1,
		)
		if default:
			frappe.throw(
				_("A default Form Layout already exists for {0}. Add a condition to this one.").format(
					layout_scope(self.dt, self.type, self.app)
				)
			)


@frappe.desk_v2_only
@frappe.whitelist()
def get_form_layouts(dt: str, type: str, app: str | None = None):
	validate_target(dt, type)
	check_layout_access(dt, type)

	layouts = get_layouts(dt, type, app)
	children = get_child_layouts(dt, app)
	if type != "Quick Entry":
		return {"layouts": layouts, "fallback": get_meta_layout(dt), "children": children}
	return {
		"layouts": layouts,
		"fallback": get_quick_entry_layout(dt),
		"dialog": opens_in_dialog(dt, layouts),
		"children": children,
	}


@frappe.desk_v2_only
@frappe.whitelist()
def save_form_layout(
	dt: str,
	type: str,
	layout: str,
	name: str | None = None,
	condition: str | None = None,
	app: str | None = None,
	title: str | None = None,
):
	validate_target(dt, type)
	if name is not None and not isinstance(name, str):
		frappe.throw(_("Form Layout name must be a string"))
	frappe.has_permission("Form Layout", "write", throw=True)
	if refuse_layout_type(dt, type):
		return None
	doc = find_layout_doc(dt, type, name, app)
	return write_layout_row(
		doc,
		dt=dt,
		type=type,
		app=app,
		layout=layout,
		condition=condition,
		title=KEEP if title is None else title,
	).name


def write_layout_row(
	doc: "FormLayout",
	*,
	dt=KEEP,
	type=KEEP,
	app=KEEP,
	layout=KEEP,
	condition=KEEP,
	title=KEEP,
	omitted=KEEP,
	dialog_size=KEEP,
) -> "FormLayout":
	"""Save the given fields on a Form Layout row and refresh its fingerprint; callers check permissions."""
	values = {
		"dt": dt,
		"type": type,
		"app": app,
		"layout": layout,
		"condition": condition,
		"title": title,
		"omitted": omitted,
		"dialog_size": dialog_size,
	}
	doc.update({field: value for field, value in values.items() if value is not KEEP})
	validate_target(doc.dt, doc.type)
	if message := layout_type_refusal(doc.dt, doc.type):
		frappe.throw(message, title=_("Layout Not Saved"))
	doc.fingerprint = source_fingerprint(doc.dt, doc.type)
	# `validate` computes it, once the layout has passed the checks that refuse a malformed one.
	doc.flags.writes_omitted = doc.type in OMITTING_LAYOUT_TYPES
	doc.save()
	return doc


def check_layout_access(dt: str, type: str) -> None:
	if frappe.is_table(dt):
		return check_child_layout_access(dt)
	if type in CREATE_LAYOUT_TYPES and frappe.has_permission(dt, "create"):
		return
	frappe.has_permission(dt, "read", throw=True)


def check_child_layout_access(dt: str) -> None:
	"""A child DocType has no rights of its own: its row dialog is read through a parent's."""
	if frappe.has_permission("DocType", "read") or frappe.has_permission("Form Layout", "read"):
		return
	parents = get_parent_doctypes([dt])[dt]
	if any(frappe.has_permission(parent, "read") and shows_as_grid(dt, parent) for parent in parents):
		return
	frappe.throw(
		_("You need read access to a DocType that has {0} as a table.").format(frappe.bold(dt)),
		frappe.PermissionError,
	)


def shows_as_grid(dt: str, parent: str) -> bool:
	"""A Table MultiSelect parent never opens a row dialog, so it grants no layout read."""
	return any(
		field.fieldtype == "Table" and field.options == dt
		for field in frappe.get_meta(parent).get_table_fields()
	)


def refuse_layout_type(dt: str, type: str) -> bool:
	"""Tell the person a child DocType has only Details and a Single is never created; return whether refused."""
	message = layout_type_refusal(dt, type)
	if message:
		frappe.msgprint(message, title=_("Layout Not Saved"), indicator="orange")
	return bool(message)


def layout_type_refusal(dt: str, type: str) -> str | None:
	meta = frappe.get_meta(dt)
	if meta.istable and type not in CHILD_LAYOUT_TYPES:
		message = _("{0} is a child table, so it has only a Details layout, which its row dialog reads.")
	elif meta.issingle and type not in SINGLE_LAYOUT_TYPES:
		message = _("{0} is a Single, which is never created, so it has no {1} layout.")
	else:
		return None
	return message.format(frappe.bold(dt), _(type))


def get_layouts(dt: str, type: str, app: str | None) -> list[dict]:
	layouts = get_row_layouts(dt, type, app)
	if not layouts and type == "New Record":
		layouts = get_row_layouts(dt, "Details", app)
	return with_app_layout(layouts, dt, type)


def get_child_layouts(dt: str, app: str | None) -> dict[str, list[dict]]:
	"""Each `Table` field's child DocType's Details rows, in one query, sent under the parent's access."""
	children = list(
		dict.fromkeys(
			field.options
			for field in frappe.get_meta(dt).get_table_fields(include_computed=True)
			if field.fieldtype == "Table"
		)
	)
	if not children:
		return {}
	rows = frappe.get_all(
		"Form Layout",
		filters={"dt": ("in", children), "type": "Details"},
		fields=["name", "dt", "app", "condition", "layout", "omitted", "title", "fingerprint"],
		order_by="creation asc",
	)
	found = {child: [] for child in children}
	for row in rows:
		found[row.dt].append(row)
	return {
		child: with_app_layout(row_layouts(rows_in_app(own, app), child, "Details"), child, "Details")
		for child, own in found.items()
	}


def with_app_layout(layouts: list[dict], dt: str, type: str) -> list[dict]:
	"""Every site row comes before the app file's layouts, and a row with no condition drops the file."""
	if any(not layout["condition"] for layout in layouts):
		return layouts
	app_layouts = read_source_app_layouts(dt, type)
	for entry in app_layouts.entries if app_layouts else ():
		layouts.append(
			{
				"name": None,
				"title": entry.title,
				"condition": entry.condition,
				"layout": parse_layout(entry.layout),
				"omitted": list(entry.omitted),
				"size": entry.size,
			}
		)
	return layouts


def read_source_app_layouts(dt: str, type: str):
	"""A New Record with no file of its own reads the Details file."""
	app_layouts = read_app_layouts(dt, type)
	if not app_layouts and type == "New Record":
		return read_app_layouts(dt, "Details")
	return app_layouts


def source_fingerprint(dt: str, type: str) -> str:
	"""The hash of what a new site row of `type` is copied from: the app file, else the fallback."""
	app_layouts = read_source_app_layouts(dt, type)
	if app_layouts:
		return app_layouts.version
	fallback = (
		get_quick_entry_layout(dt, custom=False)
		if type == "Quick Entry"
		else get_meta_layout(dt, custom=False)
	)
	return content_hash(frappe.as_json(fallback).encode())


def get_row_layouts(dt: str, type: str, app: str | None) -> list[dict]:
	return row_layouts(rows_in_app(get_layout_rows(dt, type), app), dt, type)


def row_layouts(rows: list, dt: str, type: str) -> list[dict]:
	"""The source is hashed once, and only when a row has a fingerprint to compare it with."""
	source = functools.cache(lambda: source_fingerprint(dt, type))
	return [layout_of(row, source) for row in rows]


def rows_in_app(rows: list, app: str | None) -> list:
	"""The rows naming `app` when there are any, else the rows naming none; `None` is the `/apps` index."""
	named = [row for row in rows if app and row.app == app]
	return named or [row for row in rows if not row.app]


def layout_of(row, source: Callable[[], str]) -> dict:
	layout = {
		"name": row.name,
		"title": row.title,
		"condition": row.condition,
		"layout": parse_layout(row.layout),
		"omitted": parse_omitted(row.omitted),
		"size": row.get("dialog_size"),
	}
	if row.fingerprint:
		layout["source_changed"] = row.fingerprint != source()
	return layout


def get_layout_rows(dt: str, type: str) -> list:
	return frappe.get_all(
		"Form Layout",
		filters={"dt": dt, "type": type},
		fields=["name", "app", "condition", "layout", "omitted", "dialog_size", "title", "fingerprint"],
		order_by="creation asc",
	)


def opens_in_dialog(dt: str, layouts: list) -> bool:
	"""Whether Create opens a dialog; a person who gets `False` gets the full-page new record."""
	if layouts:
		return True
	meta = frappe.get_meta(dt)
	if not meta.quick_entry:
		return False
	fields = get_quick_entry_fields(meta)
	if any(field.fieldtype == "Table" and not mandatory_condition(field) for field in fields):
		return False
	named_by_prompt = (meta.autoname or "").lower() == "prompt"
	return named_by_prompt or any(not field.hidden and not mandatory_condition(field) for field in fields)


def get_quick_entry_fields(meta, custom: bool = True) -> list:
	return quick_entry_fields(layout_fields(meta, custom))


def quick_entry_fields(fields: list) -> list:
	return [
		field
		for field in fields
		if (field.reqd or field.allow_in_quick_entry or field.mandatory_depends_on)
		and not field.read_only
		and not field.is_virtual
		and field.fieldtype not in LAYOUT_BREAKS
	]


def mandatory_condition(field) -> str | None:
	"""The condition a field is in the Quick Entry set under, or `None` when it is always there."""
	if field.reqd or field.allow_in_quick_entry:
		return None
	return field.mandatory_depends_on


def get_quick_entry_layout(dt: str, custom: bool = True) -> list:
	return quick_entry_layout(layout_fields(frappe.get_meta(dt), custom))


def quick_entry_layout(fields: list) -> list:
	sections = []
	for field in quick_entry_fields(fields):
		condition = mandatory_condition(field)
		if condition or not sections or sections[-1].get("dependsOn"):
			sections.append(new_quick_entry_section(condition))
		sections[-1]["columns"][0]["fields"].append(field.fieldname)
	if not sections:
		return []
	tabs = wrap_tabless(sections)
	name_layout_containers(tabs)
	return tabs


def new_quick_entry_section(condition: str | None) -> dict:
	section = {"hideBorder": True, "columns": [{"fields": []}]}
	if condition:
		section["dependsOn"] = condition
	return section


def publish_doctype_update(dt: str) -> None:
	"""Tell open desks that `dt`'s layouts changed, so the next visit fetches them again."""
	frappe.publish_realtime("doctype_update", {"doctype": dt}, after_commit=True)  # nosemgrep


def validate_target(dt: str, type: str) -> None:
	# A non-str `dt` would reach `get_all` as a filter operator and read every doctype's layouts.
	if not isinstance(dt, str):
		frappe.throw(_("Document Type must be a name"))
	if type not in FORM_LAYOUT_TYPES:
		frappe.throw(_("Invalid Form Layout type: {0}").format(type))


def find_layout_doc(dt: str, type: str, name: str | None, app: str | None):
	if name:
		doc = frappe.get_doc("Form Layout", name)
		if (doc.dt, doc.type, doc.app or None) != (dt, type, app or None):
			frappe.throw(
				_("Form Layout {0} belongs to {1}, not {2}").format(
					name, layout_scope(doc.dt, doc.type, doc.app), layout_scope(dt, type, app)
				)
			)
		return doc
	default = frappe.get_all("Form Layout", filters=default_filters(dt, type, app), limit=1)
	if default:
		return frappe.get_doc("Form Layout", default[0].name)
	return frappe.new_doc("Form Layout")


def default_filters(dt: str, type: str, app: str | None) -> dict:
	"""The one row of `(dt, type, app)` with no condition."""
	return {"dt": dt, "type": type, "app": app or ("is", "not set"), "condition": ("is", "not set")}


def layout_scope(dt: str, type: str, app: str | None) -> str:
	return f"{dt} ({type}, {app})" if app else f"{dt} ({type})"


def parse_layout(layout: str | None) -> list:
	"""Read a stored layout, naming any container a fixture or a raw insert left unnamed."""
	tree = json.loads(layout) if layout else []
	if not isinstance(tree, list):
		return []
	tabs = wrap_tabless(tree)
	name_layout_containers(tabs)
	return tabs


def parse_omitted(omitted: str | None) -> list[str]:
	"""Read a stored `omitted` list; the save checked its shape, so anything else reads as none."""
	try:
		entries = json.loads(omitted) if omitted else []
	except json.JSONDecodeError:
		return []
	return [entry for entry in entries if isinstance(entry, str)] if isinstance(entries, list) else []


def refuse_omitted(fieldname: str, meta: Meta) -> bool:
	"""Tell the person why `fieldname` cannot be omitted, and return whether it was refused."""
	field = meta.get_field(fieldname)
	if not field or field.fieldtype in LAYOUT_BREAKS:
		message = _("{0} is not a field of {1}, so this layout cannot omit it.")
	else:
		return False
	frappe.msgprint(
		message.format(frappe.bold(fieldname), meta.name), title=_("Field Not Omitted"), indicator="orange"
	)
	return True


def omitted_fieldnames(dt: str, tabs: list, custom: bool = True) -> list[str]:
	"""Every drawable field of `dt` the layout does not place, in meta order; an app file skips custom fields."""
	placed = {entry if isinstance(entry, str) else entry.get("fieldname") for entry in layout_entries(tabs)}
	return [
		field.fieldname
		for field in layout_fields(frappe.get_meta(dt), custom)
		if field.fieldtype not in DROPPED_FIELDTYPES and field.fieldname not in placed
	]


def wrap_tabless(tree: list) -> list:
	nodes = [node for node in tree if isinstance(node, dict)]
	if any("sections" in node for node in nodes):
		return nodes
	return [{"name": "first_tab", "sections": nodes}]


def name_layout_containers(tabs: list):
	assign_names(tabs, "tab")
	for tab in tabs:
		tab["sections"] = [section for section in tab.get("sections") or [] if isinstance(section, dict)]
		assign_names(tab["sections"], "section")
		for section in tab["sections"]:
			section["columns"] = [
				column for column in section.get("columns") or [] if isinstance(column, dict)
			]
			assign_names(section["columns"], "column")
			for column in section["columns"]:
				column["fields"] = [field for field in column.get("fields") or [] if field]


def assign_names(nodes: list, kind: str):
	taken = {node.get("name") for node in nodes if node.get("name")}
	for index, node in enumerate(nodes, start=1):
		if node.get("name"):
			continue
		name = slugify(node.get("label")) or f"{kind}_{index}"
		if name in taken:
			name = f"{name}_{index}"
		node["name"] = name
		taken.add(name)


def data_fieldnames(meta: Meta) -> set[str]:
	"""Every fieldname a script may hand to `page.fields`; a layout break is a section's own name."""
	return {field.fieldname for field in meta.fields if field.fieldtype not in LAYOUT_BREAKS}


def inline_fields(tabs: list) -> list[dict]:
	"""The fields a layout defines itself: DocField-shaped dicts beside the fieldnames."""
	return [entry for entry in layout_entries(tabs) if isinstance(entry, dict)]


def layout_entries(tabs: list) -> list:
	return [
		entry
		for tab in tabs
		for section in tab["sections"]
		for column in section["columns"]
		for entry in column["fields"]
	]


def validate_inline_field(field: dict, meta: Meta) -> None:
	fieldname, fieldtype = field.get("fieldname"), field.get("fieldtype")
	if not (fieldname and fieldtype and isinstance(fieldname, str) and isinstance(fieldtype, str)):
		frappe.throw(
			_("A field defined in the layout needs a fieldname and a fieldtype."),
			title=_("Invalid Layout"),
		)
	if fieldtype not in data_fieldtypes:
		frappe.throw(
			_("Field {0} has the fieldtype {1}, which a layout cannot define.").format(
				frappe.bold(fieldname), frappe.bold(fieldtype)
			),
			title=_("Invalid Layout"),
		)
	if fieldname in STANDARD_FIELDS:
		frappe.throw(
			_("{0} is a standard field of every document. A layout cannot define it.").format(
				frappe.bold(fieldname)
			),
			title=_("Invalid Layout"),
		)
	docfield = meta.get_field(fieldname)
	if docfield and not docfield.read_only:
		frappe.throw(
			_("{0} is already a field of {1}. Add it to the layout by its fieldname.").format(
				frappe.bold(fieldname), meta.name
			),
			title=_("Invalid Layout"),
		)


def refuse_repeated_inline_fields(tabs: list, fields: list[dict]) -> None:
	"""Refuse an inline field placed twice, by name or as a dict; both inputs would hold one value."""
	placed = [entry.get("fieldname") if isinstance(entry, dict) else entry for entry in layout_entries(tabs)]
	for field in fields:
		if placed.count(field["fieldname"]) > 1:
			frappe.throw(
				_("Field {0} is in this layout more than once.").format(frappe.bold(field["fieldname"])),
				title=_("Invalid Layout"),
			)


def refuse_section_only_keys(kind: str, container: dict):
	for key in SECTION_ONLY_KEYS:
		if key in container:
			frappe.throw(
				_("{0} {1} cannot have {2}: only a section can.").format(kind, container["name"], key),
				title=_("Invalid Layout"),
			)


def refuse_field_name(kind: str, name: str, fieldnames: set[str], dt: str):
	"""Throw when a tab or section carries a data fieldname of the doctype."""
	if name not in fieldnames:
		return
	frappe.throw(
		_("{0} '{1}' has the name of a field of {2}; a script could not tell the two apart.").format(
			kind, name, dt
		),
		title=_("Layout Name Is a Field"),
	)


def validate_unique_names(tabs: list):
	"""Refuse a layout where two tabs, two sections or two sibling columns share a name."""
	for node, kind, _taken in duplicate_names(tabs):
		frappe.throw(duplicate_message(kind, node["name"]), title=_("Duplicate Layout Name"))


def deduplicate_names(tabs: list):
	"""Rename a duplicate sibling instead of refusing, for a layout nobody authored."""
	for node, _kind, taken in duplicate_names(tabs):
		node["name"] = free_name(node["name"], taken)


def duplicate_names(tabs: list):
	"""Yield each container whose name is taken in its group, before recording it, so a caller can rename it."""
	for nodes, kind in name_groups(tabs):
		taken = set()
		for node in nodes:
			if node["name"] in taken:
				yield node, kind, taken
			taken.add(node["name"])


def name_groups(tabs: list):
	"""A script addresses a section across the whole form, so sections share one group; columns stay per section."""
	yield tabs, "tab"
	sections = [section for tab in tabs for section in tab.get("sections") or []]
	yield sections, "section"
	for section in sections:
		yield section.get("columns") or [], "column"


def free_name(name: str, taken: set) -> str:
	"""`details`, `details-2`: the spelling `identifyTabs` already gives a duplicated tab at render time."""
	suffix = 2
	while f"{name}-{suffix}" in taken:
		suffix += 1
	return f"{name}-{suffix}"


def duplicate_message(kind: str, name: str) -> str:
	name = frappe.bold(name)
	if kind == "tab":
		return _(
			"Two tabs in this layout are both named {0}. A script addresses a tab by name, so it must be unique."
		).format(name)
	if kind == "section":
		return _(
			"Two sections in this layout are both named {0}. A name must be unique among its siblings."
		).format(name)
	return _(
		"Two columns in this section are both named {0}. A name must be unique among its siblings."
	).format(name)


def slugify(label: str | None) -> str | None:
	if not label:
		return None
	return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or None


def get_meta_layout(dt: str, custom: bool = True) -> list:
	return layout_from_fields(layout_fields(frappe.get_meta(dt), custom))


def layout_from_fields(fields: list) -> list:
	"""The fallback layout: breaks open containers, every other field goes in the column open last."""
	tabs = []
	for field in fields:
		if field.fieldtype == "Tab Break":
			tabs.append(new_container(field, "sections"))
		elif field.fieldtype == "Section Break":
			ensure_tab(tabs)["sections"].append(new_container(field, "columns"))
		elif field.fieldtype == "Column Break":
			ensure_section(tabs)["columns"].append(new_container(field, "fields"))
		else:
			ensure_column(tabs)["fields"].append(field.fieldname)
	# Break fieldnames are unique already; only the synthesized `first_tab`, `section_1`
	# and `column_1` can collide with a real fieldname, so repair silently.
	deduplicate_names(tabs)
	return tabs


def layout_fields(meta: Meta, custom: bool) -> list:
	"""The meta's fields; without `custom`, the DocType's own fields, free of Custom Fields and Property Setters."""
	if custom:
		return meta.fields
	return frappe.get_cached_doc("DocType", meta.name).fields


def new_container(field, children_key: str) -> dict:
	container = {"name": field.fieldname}
	container.update({key: value for key, value in container_properties(field).items() if value})
	container[children_key] = []
	return container


def container_properties(field) -> dict:
	"""The layout node keys a break carries, under the names the layout tree uses."""
	properties = {"label": field.label, "dependsOn": field.depends_on}
	if field.fieldtype == "Section Break":
		properties |= {
			"description": field.description,
			"collapsible": bool(field.collapsible),
			"collapsibleDependsOn": field.collapsible_depends_on,
			"hideBorder": bool(field.hide_border),
		}
	return properties


def ensure_tab(tabs: list) -> dict:
	if not tabs:
		tabs.append({"name": "first_tab", "sections": []})
	return tabs[-1]


def ensure_section(tabs: list) -> dict:
	tab = ensure_tab(tabs)
	if not tab["sections"]:
		tab["sections"].append({"name": "section_1", "columns": []})
	return tab["sections"][-1]


def ensure_column(tabs: list) -> dict:
	section = ensure_section(tabs)
	if not section["columns"]:
		section["columns"].append({"name": "column_1", "fields": []})
	return section["columns"][-1]
