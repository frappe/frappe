# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""The Settings tab's edit acts in Design mode: DocType properties, the naming series and permissions."""

import frappe
from frappe import _
from frappe.core.doctype.doctype.doctype import default_permission
from frappe.custom.doctype.customize_form.customize_form import doctype_properties
from frappe.desk.doctype_editor.errors import EditError
from frappe.permissions import std_rights

# The kind is set when the DocType is created (`create.DoctypeCreate`), never on a saved one.
KIND_PROPERTIES = ("istable", "issingle", "is_submittable", "is_tree")
DROPPED_PROPERTIES = ("hide_toolbar", "show_preview_popup")
CUSTOMIZE_PROPERTIES = tuple(
	property for property in doctype_properties if property not in (*KIND_PROPERTIES, *DROPPED_PROPERTIES)
)
DESIGN_PROPERTIES = (*CUSTOMIZE_PROPERTIES, "description", "track_seen", "allow_rename")
# Ticking a right ticks these; unticking one of them unticks the rights that need it (`validate_permissions`).
PREREQUISITES = {
	"cancel": ("submit",),
	"submit": ("write",),
	"amend": ("write", "create"),
	"import": ("create",),
}
AUTOINCREMENT = "autoincrement"
# A permission row's key and its ticks: the rights and `mask`, which v1's Role Permissions Manager sets.
PERMISSION_COLUMNS = ("role", "permlevel", "if_owner", *std_rights, "mask")


class SettingsEdits:
	properties = DESIGN_PROPERTIES

	def settings_set_doctype_property(self, edit: dict):
		property, value = edit.get("property"), edit.get("value")
		self.refuse_property(property)
		if property == "autoname":
			self.refuse_autoincrement(value)
		self.state.doc.set(property, value)
		if property == "is_submittable":
			self.follow_kind(value)

	def settings_set_naming_series(self, edit: dict):
		options = [option.strip() for option in edit.get("options") or []]
		if not options or not all(options) or len(set(options)) < len(options):
			raise setting_error(_("Give each naming series once, and none empty."), "naming_series")
		default = edit.get("default") or options[0]
		if default not in options:
			raise setting_error(_("The default series must be one of the list."), "naming_series")
		field = self.series_field()
		field.options, field.default = "\n".join(options), default

	def settings_add_permission(self, edit: dict):
		key = permission_key(edit)
		if self.permission(key, missing_ok=True):
			raise setting_error(_("{0} already has a row at level {1}.").format(*key[:2]), "permissions")
		# DocPerm's defaults tick most rights; a new row starts with read only.
		rights = {**dict.fromkeys(std_rights, 0), "read": 1}
		self.append_permission({**rights, "role": key[0], "permlevel": key[1], "if_owner": key[2]})

	def settings_remove_permission(self, edit: dict):
		self.drop_permission(self.permission(permission_key(edit)))

	def settings_set_permission(self, edit: dict):
		right = edit.get("right")
		if right not in std_rights:
			raise setting_error(_("{0} is not a permission.").format(right), "permissions")
		row = self.permission(permission_key(edit))
		for each in closure(right, bool(edit.get("value"))):
			row.set(each, 1 if edit.get("value") else 0)

	def follow_kind(self, submittable):
		"""The default rule gets Submit as `before_insert` gives it, while no edit has changed it."""
		default = default_permission(False)
		for row in self.permission_rows():
			if permission_key(row) == ("System Manager", 0, 0) and all(
				int(row.get(right) or 0) == default.get(right, 0) for right in std_rights if right != "submit"
			):
				row.submit = 1 if submittable else 0

	def refuse_property(self, property: str):
		# The create folded the kind into its insert, so the edit sets the value the DocType has.
		if property in KIND_PROPERTIES:
			if self.state.created:
				return
			raise setting_error(_("{0} is set when the DocType is created.").format(property), property)
		if property not in self.properties:
			raise setting_error(_("{0} is not a DocType setting the editor sets.").format(property), property)

	def refuse_autoincrement(self, value: str):
		"""The DocType's save refuses it too, after its DDL; this names the edit."""
		if AUTOINCREMENT not in (value, self.saved_autoname()) or value == self.saved_autoname():
			return
		if not frappe.get_meta(self.state.name).issingle and frappe.get_all(self.state.name, limit=1):
			raise setting_error(
				_("Number in order can only be switched to or from while there are no records."), "autoname"
			)

	def saved_autoname(self) -> str | None:
		return frappe.db.get_value("DocType", self.state.name, "autoname")

	def series_field(self):
		"""Design adds the naming_series field the rule needs when the DocType has none."""
		if field := self.state.doc.get("fields", {"fieldname": "naming_series"}):
			return field[0]
		self.fields_add_field(
			{"label": "Series", "fieldname": "naming_series", "fieldtype": "Select", **self.first_column()}
		)
		field = self.state.field("naming_series")
		field.reqd = 1
		return field

	def first_column(self) -> dict:
		"""Where the canvas puts the series field: first in the Details layout's first column."""
		if self.state.type_refusal("Details"):
			return {}
		details = {"type": "Details"}
		tabs = self.state.layout(details).tree.tabs
		sections = tabs[0]["sections"] if tabs else []
		if not sections or not sections[0]["columns"]:
			return {}
		column = sections[0]["columns"][0]["name"]
		return {"layout": details, "section": sections[0]["name"], "column": column, "index": 0}

	def permission_rows(self) -> list:
		return self.state.doc.permissions

	def append_permission(self, values: dict):
		self.state.doc.append("permissions", values)

	def drop_permission(self, row):
		self.state.doc.remove(row)

	def permission(self, key: tuple, missing_ok: bool = False):
		row = next((row for row in self.permission_rows() if permission_key(row) == key), None)
		if not row and not missing_ok:
			raise setting_error(_("{0} has no row at level {1}.").format(*key[:2]), "permissions")
		return row


def permission_key(row) -> tuple:
	if not row.get("role"):
		raise setting_error(_("A permission row needs a role."), "permissions")
	return row.get("role"), int(row.get("permlevel") or 0), int(row.get("if_owner") or 0)


def closure(right: str, ticked: bool) -> set[str]:
	"""The right with its prerequisites when ticked, or with its dependents when unticked."""
	found, todo = set(), [right]
	while todo:
		each = todo.pop()
		found.add(each)
		if ticked:
			todo += [need for need in PREREQUISITES.get(each, ()) if need not in found]
		else:
			todo += [right for right, needs in PREREQUISITES.items() if each in needs and right not in found]
	return found


def setting_error(message: str, property: str) -> EditError:
	return EditError(message, kind="setting", property=property)
