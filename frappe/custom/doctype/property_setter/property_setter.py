# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _

from frappe.model.document import Document

not_allowed_fieldtype_change = ['naming_series']

class PropertySetter(Document):
	def autoname(self):
		self.name = '{doctype}-{field}-{property}'.format(
			doctype = self.doc_type,
			field = self.field_name or self.row_name or 'main',
			property = self.property
		)

	def validate(self):
		self.validate_fieldtype_change()
		if self.is_new():
			delete_property_setter(self.doc_type, self.property, self.field_name)

		# clear cache
		frappe.clear_cache(doctype = self.doc_type)

	def validate_fieldtype_change(self):
		if self.field_name in not_allowed_fieldtype_change and \
			self.property == 'fieldtype':
			frappe.throw(_("Field type cannot be changed for {0}").format(self.field_name))

	def get_property_list(self, dt):
		return frappe.db.get_all('DocField',
			fields=['fieldname', 'label', 'fieldtype'],
			filters={
				'parent': dt,
				'fieldtype': ['not in', ('Section Break', 'Column Break', 'Tab Break', 'HTML', 'Read Only', 'Fold') + frappe.model.table_fields],
				'fieldname': ['!=', '']
			},
			order_by='label asc',
			as_dict=1
		)

	def get_setup_data(self):
		return {
			'doctypes': frappe.get_all("DocType", pluck="name"),
			'dt_properties': self.get_property_list('DocType'),
			'df_properties': self.get_property_list('DocField')
		}

	def get_field_ids(self):
		return frappe.db.get_values(
			"DocField",
			filters={"parent": self.doc_type},
			fieldname=["name", "fieldtype", "label", "fieldname"],
			as_dict=True,
		)

	def get_defaults(self):
		if not self.field_name:
			return frappe.get_all("DocType", filters={"name": self.doc_type}, fields="*")[0]
		else:
			return frappe.db.get_values(
				"DocField",
				filters={"fieldname": self.field_name, "parent": self.doc_type},
				fieldname="*",
			)[0]

	def on_update(self):
		if frappe.flags.in_patch:
			self.flags.validate_fields_for_doctype = False

		if not self.flags.ignore_validate and self.flags.validate_fields_for_doctype:
			from frappe.core.doctype.doctype.doctype import validate_fields_for_doctype
			validate_fields_for_doctype(self.doc_type)

def make_property_setter(doctype, fieldname, property, value, property_type, for_doctype = False,
		validate_fields_for_doctype=True):
	# WARNING: Ignores Permissions
	property_setter = frappe.get_doc({
		"doctype":"Property Setter",
		"doctype_or_field": for_doctype and "DocType" or "DocField",
		"doc_type": doctype,
		"field_name": fieldname,
		"property": property,
		"value": value,
		"property_type": property_type
	})
	property_setter.flags.ignore_permissions = True
	property_setter.flags.validate_fields_for_doctype = validate_fields_for_doctype
	property_setter.insert()
	return property_setter

def delete_property_setter(doc_type, property, field_name=None):
	"""delete other property setters on this, if this is new"""
	filters = dict(doc_type = doc_type, property=property)
	if field_name:
		filters['field_name'] = field_name

	frappe.db.delete('Property Setter', filters)

