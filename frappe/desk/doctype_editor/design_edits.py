# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""Each Design edit act applied to a `DesignState` in memory (inventory section A)."""

import frappe
from frappe import _
from frappe.database.schema import SPECIAL_CHAR_PATTERN
from frappe.desk.doctype.form_layout.form_layout import LAYOUT_BREAKS
from frappe.desk.doctype_editor.design_state import DesignState
from frappe.desk.doctype_editor.errors import EditError, field_error
from frappe.desk.doctype_editor.settings_edits import SettingsEdits
from frappe.model import child_table_fields, default_fields, no_value_fields, table_fields

RESERVED_PROPERTIES = ("name", "parent", "parenttype", "parentfield", "idx", "doctype")
PLACE_KEYS = ("fieldname", "section", "column", "index", "tab")
UNFETCHABLE_TYPES = (*no_value_fields, "Dynamic Link")
# A column is named with its section: column names repeat across sections.
CANVAS_ACTS = {
	"canvas.add_tab": ("add_tab", ("name", "label", "index")),
	"canvas.remove_tab": ("remove_tab", ("tab",)),
	"canvas.move_tab": ("move_tab", ("tab", "index")),
	"canvas.add_section": ("add_section", ("tab", "name", "label", "index")),
	"canvas.remove_section": ("remove_section", ("section",)),
	"canvas.move_section": ("move_section", ("section", "tab", "index")),
	"canvas.add_column": ("add_column", ("section", "name", "index")),
	"canvas.remove_column": ("remove_column", ("column", "section")),
	"canvas.move_column": ("move_column", ("column", "section", "to_section", "index")),
	"canvas.set_container_property": (
		"set_container_property",
		("container", "section", "property", "value"),
	),
	"canvas.place_field": ("place_field", PLACE_KEYS),
	"canvas.move_field": ("place_field", PLACE_KEYS),
	"canvas.unplace_field": ("unplace_field", ("fieldname",)),
}


class DesignEdits(SettingsEdits):
	def __init__(self, state: DesignState):
		self.state = state

	def apply(self, edit: dict):
		act = edit.get("act") if isinstance(edit, dict) else None
		if act in CANVAS_ACTS:
			return self.canvas(edit, *CANVAS_ACTS[act])
		method = getattr(self, (act or "").replace(".", "_"), None)
		if not method or not act.startswith(("fields.", "layouts.", "settings.")):
			raise EditError(_("{0} is not a Design edit.").format(act))
		method(edit)

	def canvas(self, edit: dict, method: str, keys: tuple):
		layout = self.state.layout(edit.get("layout"))
		if "fieldname" in keys:
			self.state.field(edit.get("fieldname"))
		getattr(layout.tree, method)(**{key: edit.get(key) for key in keys if key in edit})

	def fields_add_field(self, edit: dict):
		label, fieldtype = edit.get("label"), edit.get("fieldtype")
		if not label or not fieldtype:
			raise EditError(_("A new field needs a label and a type."))
		fieldname = edit.get("fieldname") or SPECIAL_CHAR_PATTERN.sub("", frappe.scrub(label))
		self.state.refuse_taken_fieldname(fieldname)
		properties = edit.get("properties") or {}
		for property in properties:
			refuse_property(fieldname, property)
		field = self.state.doc.append(
			"fields",
			{
				**properties,
				"fieldname": fieldname,
				"label": label,
				"fieldtype": fieldtype,
				"options": edit.get("options"),
			},
		)
		self.state.refuse_deleted_table_rows(field, fieldname)
		if edit.get("layout"):
			self.canvas({**edit, "fieldname": fieldname}, "place_field", PLACE_KEYS)
		elif fieldtype not in LAYOUT_BREAKS:
			self.state.touch_omitting_layouts()

	def fields_set_field_property(self, edit: dict):
		fieldname, property = edit.get("fieldname"), edit.get("property")
		field = self.state.field(fieldname)
		refuse_property(fieldname, property)
		if property == "options":
			self.refuse_moving_table(field, edit.get("value"))
		field.set(property, edit.get("value"))

	def fields_reorder_field(self, edit: dict):
		field = self.state.field(edit.get("fieldname"))
		fields = self.state.doc.fields
		fields.remove(field)
		index = edit.get("index")
		fields.insert(len(fields) if index is None else index, field)
		for idx, each in enumerate(fields, start=1):
			each.idx = idx

	def fields_fetch_field(self, edit: dict):
		"""A read-only field filled from a field of the record a Link names, typed like that field."""
		link = self.state.field(edit.get("link"))
		if link.fieldtype != "Link" or not link.options:
			raise field_error(_("{0} is not a Link field.").format(link.fieldname), link.fieldname)
		source = frappe.get_meta(link.options).get_field(edit.get("source") or "")
		if not source:
			raise field_error(
				_("{0} has no field {1}.").format(link.options, edit.get("source")), link.fieldname
			)
		if source.fieldtype in UNFETCHABLE_TYPES:
			raise field_error(_("A {0} field cannot be fetched.").format(_(source.fieldtype)), link.fieldname)
		self.fields_add_field(
			{
				**edit,
				"label": edit.get("label") or source.label,
				"fieldname": edit.get("fieldname") or source.fieldname,
				"fieldtype": source.fieldtype,
				"options": source.options,
				"properties": {"fetch_from": f"{link.fieldname}.{source.fieldname}", "read_only": 1},
			}
		)

	def fields_delete_field(self, edit: dict):
		self.state.delete_field(edit.get("fieldname"))

	def fields_rename_field(self, edit: dict):
		self.state.rename_field(edit.get("fieldname"), edit.get("new_fieldname"))

	def fields_add_child_table(self, edit: dict):
		"""A child with `link` holds that one Link field, for a Table MultiSelect."""
		name, link = edit.get("name"), edit.get("link")
		if not name or not edit.get("table_field"):
			raise EditError(_("A new child table needs a name and a table field."))
		if link and (
			not isinstance(link, str) or not frappe.db.exists("DocType", {"name": link, "istable": 0})
		):
			raise EditError(_("{0} is not a DocType a field can link to.").format(link))
		child = self.state.add_child(name)
		if link:
			fieldname = SPECIAL_CHAR_PATTERN.sub("", frappe.scrub(link))
			if fieldname in (*default_fields, *child_table_fields):
				fieldname = f"{fieldname}_link"
			child.doc.append(
				"fields",
				{
					"fieldname": fieldname,
					"label": link,
					"fieldtype": "Link",
					"options": link,
					"in_list_view": 1,
				},
			)
		if table := self.state.doc.get("fields", {"fieldname": edit["table_field"]}):
			if (table[0].fieldtype == "Table MultiSelect") != bool(link):
				message = _("{0} needs a child table that fits its type.")
				raise field_error(message.format(table[0].fieldname), table[0].fieldname, "options")
			return self.fill_table_field(table[0], name)
		self.fields_add_field(
			{
				**edit,
				"fieldname": edit["table_field"],
				"label": edit.get("label") or name,
				"fieldtype": "Table MultiSelect" if link else "Table",
				"options": name,
			}
		)

	def fill_table_field(self, field, name: str):
		if field.fieldtype not in table_fields:
			raise field_error(_("{0} is not a Table field.").format(field.fieldname), field.fieldname)
		self.refuse_moving_table(field, name)
		field.options = name

	def refuse_moving_table(self, field, options: str | None):
		"""A saved Table field's rows stay in its saved child table, so a field with rows keeps it."""
		saved = self.state.saved_name(field.fieldname)
		saved_field = saved and frappe.get_meta(self.state.name).get_field(saved)
		if not saved_field or saved_field.fieldtype not in table_fields or saved_field.options == options:
			return
		if frappe.db.exists(saved_field.options, {"parenttype": self.state.name, "parentfield": saved}):
			message = _("{0} has rows in {1}, so it cannot point at another child table.")
			raise field_error(
				message.format(field.label or field.fieldname, saved_field.options),
				field.fieldname,
				"options",
			)

	def layouts_add(self, edit: dict):
		self.state.add_layout(
			edit.get("type"),
			edit.get("id"),
			edit.get("title"),
			edit.get("condition"),
			edit.get("start") or "copy",
		)

	def layouts_rename(self, edit: dict):
		self.state.layout(edit.get("layout")).title = edit.get("title")

	def layouts_set_condition(self, edit: dict):
		self.state.layout(edit.get("layout")).condition = edit.get("condition")

	def layouts_delete(self, edit: dict):
		layout = self.state.layout(edit.get("layout"))
		if not layout.condition:
			raise EditError(
				_("The default {0} layout cannot be deleted.").format(_(layout.type)),
				kind="layout",
				layout=layout.id,
			)
		layout.deleted = True


def refuse_property(fieldname: str, property: str):
	if property == "fieldname":
		raise field_error(_("Rename the field to change its fieldname."), fieldname, property)
	if property in RESERVED_PROPERTIES or not frappe.get_meta("DocField").has_field(property):
		raise field_error(_("{0} is not a field property.").format(property), fieldname, property)
