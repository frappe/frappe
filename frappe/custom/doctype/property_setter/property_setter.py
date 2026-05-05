# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document

not_allowed_fieldtype_change = ["naming_series"]


class PropertySetter(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		default_value: DF.Data | None
		doc_type: DF.Link
		doctype_or_field: DF.Literal[
			"", "DocField", "DocType", "DocType Link", "DocType Action", "DocType State"
		]
		field_name: DF.Data | None
		is_system_generated: DF.Check
		module: DF.Link | None
		property: DF.Data
		property_type: DF.Data | None
		row_name: DF.Data | None
		value: DF.SmallText | None
	# end: auto-generated types

	def autoname(self):
		self.name = "{doctype}-{field}-{property}".format(
			doctype=self.doc_type, field=self.field_name or self.row_name or "main", property=self.property
		)

	def validate(self):
		self.validate_fieldtype_change()

		if self.is_new():
			delete_property_setter(self.doc_type, self.property, self.field_name, self.row_name)

		frappe.clear_cache(doctype=self.doc_type)

	def on_trash(self):
		frappe.clear_cache(doctype=self.doc_type)

	def validate_fieldtype_change(self):
		if self.property == "fieldtype" and self.field_name in not_allowed_fieldtype_change:
			frappe.throw(_("Field type cannot be changed for {0}").format(self.field_name))

	def on_update(self):
		if frappe.flags.in_patch:
			self.flags.validate_fields_for_doctype = False

		if not self.flags.ignore_validate and self.flags.validate_fields_for_doctype:
			from frappe.core.doctype.doctype.doctype import validate_fields_for_doctype

			validate_fields_for_doctype(self.doc_type)

	def get_permission_log_options(self, event=None):
		if self.property in ("ignore_user_permissions", "permlevel"):
			return {
				"for_doctype": "DocType",
				"for_document": self.doc_type,
				"fields": ("value", "property", "field_name"),
			}

		self._no_perm_log = True


def make_property_setter(
	doctype,
	fieldname,
	property,
	value,
	property_type,
	for_doctype=False,
	validate_fields_for_doctype=True,
	is_system_generated=True,
):
	# WARNING: Ignores Permissions
	property_setter = frappe.get_doc(
		{
			"doctype": "Property Setter",
			"doctype_or_field": (for_doctype and "DocType") or "DocField",
			"doc_type": doctype,
			"field_name": fieldname,
			"property": property,
			"value": value,
			"property_type": property_type,
			"is_system_generated": is_system_generated,
		}
	)
	property_setter.flags.ignore_permissions = True
	property_setter.flags.validate_fields_for_doctype = validate_fields_for_doctype
	property_setter.insert()
	return property_setter


def delete_property_setter(doc_type, property=None, field_name=None, row_name=None):
	"""delete other property setters on this, if this is new"""
	filters = {"doc_type": doc_type}
	if property:
		filters["property"] = property

	if field_name:
		filters["field_name"] = field_name
	if row_name:
		filters["row_name"] = row_name

	_delete_property_setters(filters)


def bulk_delete_property_setters(property_setters: list[dict], bypass_hooks: bool = False):
	"""
	Delete property setters.

	:param property_setters: List of filters for Property Setter rows.
	:param bypass_hooks: If `True`, raw delete without doc hooks.

	Example of `property_setters`:
	```
	[
	    {"doctype": "ToDo", "fieldname": "status", "property": "hidden"},
	    {"doctype": "ToDo", "fieldname": "status", "property": "read_only"},
	]
	```

	---

	Note: `doctype` and `fieldname` are mandatory.
	"""
	field_map = {
		"doctype": "doc_type",
		"fieldname": "field_name",
	}

	doctypes_to_clear = set()

	for property_setter in property_setters:
		filters = property_setter.copy()

		for key, fieldname in field_map.items():
			if key in filters:
				filters[fieldname] = filters.pop(key)

		if not filters:
			continue

		if not filters.get("doc_type") or not filters.get("field_name"):
			frappe.throw(_("`doctype` and `fieldname` are required for deleting property setters."))

		if bypass_hooks:
			frappe.db.delete("Property Setter", filters)
			doctypes_to_clear.add(filters["doc_type"])
		else:
			_delete_property_setters(filters)

	for doctype in doctypes_to_clear:
		frappe.clear_cache(doctype=doctype)


def _delete_property_setters(filters: dict):
	property_setters = frappe.get_all("Property Setter", filters=filters, pluck="name")

	for ps in property_setters:
		frappe.get_doc("Property Setter", ps).delete(ignore_permissions=True, force=True)
