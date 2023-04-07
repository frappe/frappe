# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document

not_allowed_fieldtype_change = ["naming_series"]


class PropertySetter(Document):
	def autoname(self):
		self.name = "{doctype}-{field}-{property}".format(
			doctype=self.doc_type, field=self.field_name or self.row_name or "main", property=self.property
		)

	def validate(self):
		self.validate_fieldtype_change()
		self.validate_default_value()

		if self.is_new():
			delete_property_setter(self.doc_type, self.property, self.field_name, self.row_name)
		frappe.clear_cache(doctype=self.doc_type)

	def validate_fieldtype_change(self):
		if self.property == "fieldtype" and self.field_name in not_allowed_fieldtype_change:
			frappe.throw(_("Field type cannot be changed for {0}").format(self.field_name))

	def validate_default_value(self):
		if self.property == "default":
			field_meta = frappe.get_meta(self.doc_type).get_field(self.field_name)
			fieldtype = field_meta.fieldtype
			label = field_meta.label

			if fieldtype == "Int":
				try:
					int(self.value)
				except ValueError:
					frappe.throw(
						_("Default value for field {0} must be an integer").format(frappe.bold(label)),
						title=_("Invalid Value"),
					)
			elif fieldtype in ["Percent", "Float"]:
				try:
					float(self.value)
				except ValueError:
					frappe.throw(
						_("Default value for field {0} must be a number").format(frappe.bold(label)),
						title=_("Invalid Value"),
					)

	def on_update(self):
		if frappe.flags.in_patch:
			self.flags.validate_fields_for_doctype = False

		if not self.flags.ignore_validate and self.flags.validate_fields_for_doctype:
			from frappe.core.doctype.doctype.doctype import validate_fields_for_doctype

			validate_fields_for_doctype(self.doc_type)


def make_property_setter(
	doctype,
	fieldname,
	property,
	value,
	property_type,
	for_doctype=False,
	validate_fields_for_doctype=True,
):
	# WARNING: Ignores Permissions
	property_setter = frappe.get_doc(
		{
			"doctype": "Property Setter",
			"doctype_or_field": for_doctype and "DocType" or "DocField",
			"doc_type": doctype,
			"field_name": fieldname,
			"property": property,
			"value": value,
			"property_type": property_type,
		}
	)
	property_setter.flags.ignore_permissions = True
	property_setter.flags.validate_fields_for_doctype = validate_fields_for_doctype
	property_setter.insert()
	return property_setter


def delete_property_setter(doc_type, property, field_name=None, row_name=None):
	"""delete other property setters on this, if this is new"""
	filters = dict(doc_type=doc_type, property=property)
	if field_name:
		filters["field_name"] = field_name
	if row_name:
		filters["row_name"] = row_name

	frappe.db.delete("Property Setter", filters)
