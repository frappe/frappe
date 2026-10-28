# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import copy
import json
import re

import frappe
from frappe import _
from frappe.model import child_table_fields, data_fieldtypes, default_fields, optional_fields
from frappe.model.document import Document
from frappe.model.meta import Meta

FORM_LAYOUT_TYPES = ("Details", "Side Panel", "Quick Entry", "New Record")
CREATE_LAYOUT_TYPES = ("Quick Entry", "New Record")
LAYOUT_BREAKS = ("Section Break", "Column Break", "Tab Break")
STANDARD_FIELDS = frozenset(default_fields + child_table_fields + optional_fields)


class FormLayout(Document):
	def validate(self):
		self.validate_single_default()
		self.name_layout()
		tabs = parse_layout(self.layout)
		self.validate_inline_fields(tabs)
		self.validate_names_are_not_fields(tabs)

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
		fieldnames = data_fieldnames(self.dt) | {field["fieldname"] for field in inline_fields(tabs)}
		for tab in tabs:
			refuse_field_name(_("Tab"), tab["name"], fieldnames, self.dt)
			for section in tab["sections"]:
				refuse_field_name(_("Section"), section["name"], fieldnames, self.dt)

	def validate_inline_fields(self, tabs: list):
		fields = inline_fields(tabs)
		if not fields:
			return
		if self.type not in CREATE_LAYOUT_TYPES:
			frappe.throw(
				_("Only a Quick Entry or New Record layout can define a field of its own."),
				title=_("Invalid Layout"),
			)
		meta = frappe.get_meta(self.dt)
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

	def validate_single_default(self):
		if self.condition:
			return
		default = frappe.get_all(
			"Form Layout",
			filters={
				"dt": self.dt,
				"type": self.type,
				"condition": ("is", "not set"),
				"name": ("!=", self.name or ""),
			},
			limit=1,
		)
		if default:
			frappe.throw(
				_("A default Form Layout already exists for {0} ({1}). Add a condition to this one.").format(
					self.dt, self.type
				)
			)


@frappe.desk_v2_only
@frappe.whitelist()
def get_form_layouts(dt: str, type: str):
	validate_target(dt, type)
	check_layout_access(dt, type)

	rows = get_layout_rows(dt, type)
	if not rows and type == "New Record":
		rows = get_layout_rows(dt, "Details")
	layouts = [
		{"name": row.name, "condition": row.condition, "layout": parse_layout(row.layout)} for row in rows
	]
	if type != "Quick Entry":
		return {"layouts": layouts, "fallback": get_meta_layout(dt)}
	return {"layouts": layouts, "fallback": get_quick_entry_layout(dt), "dialog": opens_in_dialog(dt, rows)}


@frappe.desk_v2_only
@frappe.whitelist()
def save_form_layout(dt: str, type: str, layout: str, name: str | None = None, condition: str | None = None):
	validate_target(dt, type)
	if name is not None and not isinstance(name, str):
		frappe.throw(_("Form Layout name must be a string"))
	frappe.has_permission("Form Layout", "write", throw=True)
	doc = find_layout_doc(dt, type, name)
	doc.update({"dt": dt, "type": type, "layout": layout, "condition": condition})
	doc.save()
	return doc.name


def check_layout_access(dt: str, type: str) -> None:
	if type in CREATE_LAYOUT_TYPES and frappe.has_permission(dt, "create"):
		return
	frappe.has_permission(dt, "read", throw=True)


def get_layout_rows(dt: str, type: str) -> list:
	return frappe.get_all(
		"Form Layout",
		filters={"dt": dt, "type": type},
		fields=["name", "condition", "layout"],
		order_by="creation asc",
	)


def opens_in_dialog(dt: str, rows: list) -> bool:
	"""Whether Create opens a dialog; a person who gets `False` gets the full-page new record."""
	if rows:
		return True
	meta = frappe.get_meta(dt)
	if not meta.quick_entry:
		return False
	fields = get_quick_entry_fields(meta)
	if any(field.fieldtype == "Table" and not mandatory_condition(field) for field in fields):
		return False
	named_by_prompt = (meta.autoname or "").lower() == "prompt"
	return named_by_prompt or any(not field.hidden and not mandatory_condition(field) for field in fields)


def get_quick_entry_fields(meta) -> list:
	return [
		field
		for field in meta.fields
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


def get_quick_entry_layout(dt: str) -> list:
	sections = []
	for field in get_quick_entry_fields(frappe.get_meta(dt)):
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


def find_layout_doc(dt: str, type: str, name: str | None):
	if name:
		doc = frappe.get_doc("Form Layout", name)
		if doc.dt != dt or doc.type != type:
			frappe.throw(
				_("Form Layout {0} belongs to {1} ({2}), not {3} ({4})").format(
					name, doc.dt, doc.type, dt, type
				)
			)
		return doc
	default = frappe.get_all(
		"Form Layout", filters={"dt": dt, "type": type, "condition": ("is", "not set")}, limit=1
	)
	if default:
		return frappe.get_doc("Form Layout", default[0].name)
	return frappe.new_doc("Form Layout")


def parse_layout(layout: str | None) -> list:
	"""Read a stored layout, naming any container a fixture or a raw insert left unnamed."""
	tree = json.loads(layout) if layout else []
	if not isinstance(tree, list):
		return []
	tabs = wrap_tabless(tree)
	name_layout_containers(tabs)
	return tabs


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


def data_fieldnames(dt: str) -> set[str]:
	"""Every fieldname a script may hand to `page.fields`; a layout break is a section's own name."""
	return {field.fieldname for field in frappe.get_meta(dt).fields if field.fieldtype not in LAYOUT_BREAKS}


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


def get_meta_layout(dt: str) -> list:
	tabs = []
	for field in frappe.get_meta(dt).fields:
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


def new_container(field, children_key: str) -> dict:
	container = {"name": field.fieldname, children_key: []}
	if field.label:
		container["label"] = field.label
	return container


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
