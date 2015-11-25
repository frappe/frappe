# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""
	Customize Form is a Single DocType used to mask the Property Setter
	Thus providing a better UI from user perspective
"""
import frappe, json
from frappe import _
from frappe.utils import cint
from frappe.model.document import Document
from frappe.model import no_value_fields
from frappe.core.doctype.doctype.doctype import validate_fields_for_doctype

doctype_properties = {
	'search_fields': 'Data',
	'title_field': 'Data',
	'sort_field': 'Data',
	'sort_order': 'Data',
	'default_print_format': 'Data',
	'read_only_onload': 'Check',
	'allow_copy': 'Check',
	'max_attachments': 'Int'
}

docfield_properties = {
	'idx': 'Int',
	'label': 'Data',
	'fieldtype': 'Select',
	'options': 'Text',
	'permlevel': 'Int',
	'width': 'Data',
	'print_width': 'Data',
	'reqd': 'Check',
	'unique': 'Check',
	'ignore_user_permissions': 'Check',
	'in_filter': 'Check',
	'in_list_view': 'Check',
	'hidden': 'Check',
	'collapsible': 'Check',
	'collapsible_depends_on': 'Data',
	'print_hide': 'Check',
	'print_hide_if_no_value': 'Check',
	'report_hide': 'Check',
	'allow_on_submit': 'Check',
	'depends_on': 'Data',
	'description': 'Text',
	'default': 'Text',
	'precision': 'Select',
	'read_only': 'Check',
	'length': 'Int'
}

allowed_fieldtype_change = (('Currency', 'Float', 'Percent'), ('Small Text', 'Data'),
	('Text', 'Text Editor', 'Code'), ('Data', 'Select'), ('Text', 'Small Text'))

class CustomizeForm(Document):
	def on_update(self):
		frappe.db.sql("delete from tabSingles where doctype='Customize Form'")
		frappe.db.sql("delete from `tabCustomize Form Field`")

	def fetch_to_customize(self):
		self.clear_existing_doc()
		if not self.doc_type:
			return

		meta = frappe.get_meta(self.doc_type)

		# doctype properties
		for property in doctype_properties:
			self.set(property, meta.get(property))

		for d in meta.get("fields"):
			new_d = {"fieldname": d.fieldname, "is_custom_field": d.get("is_custom_field"), "name": d.name}
			for property in docfield_properties:
				new_d[property] = d.get(property)
			self.append("fields", new_d)

		# NOTE doc is sent to clientside by run_method

	def clear_existing_doc(self):
		doc_type = self.doc_type

		for fieldname in self.meta.get_valid_columns():
			self.set(fieldname, None)

		for df in self.meta.get_table_fields():
			self.set(df.fieldname, [])

		self.doc_type = doc_type
		self.name = "Customize Form"

	def save_customization(self):
		if not self.doc_type:
			return

		self.set_property_setters()
		self.update_custom_fields()
		self.set_idx_property_setter()
		validate_fields_for_doctype(self.doc_type)

		frappe.msgprint(_("{0} updated").format(_(self.doc_type)))
		frappe.clear_cache(doctype=self.doc_type)
		self.fetch_to_customize()

	def set_property_setters(self):
		meta = frappe.get_meta(self.doc_type)
		# doctype property setters
		for property in doctype_properties:
			if self.get(property) != meta.get(property):
				self.make_property_setter(property=property, value=self.get(property),
					property_type=doctype_properties[property])

		update_db = False
		for df in self.get("fields"):
			if df.get("__islocal"):
				continue

			meta_df = meta.get("fields", {"fieldname": df.fieldname})

			if not meta_df or meta_df[0].get("is_custom_field"):
				continue

			for property in docfield_properties:
				if property != "idx" and df.get(property) != meta_df[0].get(property):
					if property == "fieldtype":
						self.validate_fieldtype_change(df, meta_df[0].get(property), df.get(property))

					elif property == "allow_on_submit" and df.get(property):
						frappe.msgprint(_("Row {0}: Not allowed to enable Allow on Submit for standard fields")\
							.format(df.idx))
						continue
					elif property == "in_list_view" and df.get(property) \
						and df.fieldtype!="Image" and df.fieldtype in no_value_fields:
								frappe.msgprint(_("'In List View' not allowed for type {0} in row {1}")
									.format(df.fieldtype, df.idx))
								continue

					elif property == "precision" and cint(df.get("precision")) > 6 \
							and cint(df.get("precision")) > cint(meta_df[0].get("precision")):
						update_db = True

					elif property == "unique":
						update_db = True

					elif (property == "read_only" and cint(df.get("read_only"))==0
						and frappe.db.get_value("DocField", {"parent": self.doc_type, "fieldname": df.fieldname}, "read_only")==1):
						# if docfield has read_only checked and user is trying to make it editable, don't allow it
						frappe.msgprint(_("You cannot unset 'Read Only' for field {0}").format(df.label))
						continue

					self.make_property_setter(property=property, value=df.get(property),
						property_type=docfield_properties[property], fieldname=df.fieldname)

		if update_db:
			from frappe.model.db_schema import updatedb
			updatedb(self.doc_type)

	def update_custom_fields(self):
		for df in self.get("fields"):
			if df.get("__islocal"):
				self.add_custom_field(df)
			else:
				self.update_in_custom_field(df)

		self.delete_custom_fields()

	def add_custom_field(self, df):
		d = frappe.new_doc("Custom Field")
		d.dt = self.doc_type
		for property in docfield_properties:
			d.set(property, df.get(property))
		d.insert()
		df.fieldname = d.fieldname

	def update_in_custom_field(self, df):
		meta = frappe.get_meta(self.doc_type)
		meta_df = meta.get("fields", {"fieldname": df.fieldname})
		if not (meta_df and meta_df[0].get("is_custom_field")):
			return

		custom_field = frappe.get_doc("Custom Field", meta_df[0].name)
		changed = False
		for property in docfield_properties:
			if df.get(property) != custom_field.get(property):
				if property == "fieldtype":
					self.validate_fieldtype_change(df, meta_df[0].get(property), df.get(property))

				custom_field.set(property, df.get(property))
				changed = True

		if changed:
			custom_field.flags.ignore_validate = True
			custom_field.save()

	def delete_custom_fields(self):
		meta = frappe.get_meta(self.doc_type)
		fields_to_remove = (set([df.fieldname for df in meta.get("fields")])
			- set(df.fieldname for df in self.get("fields")))

		for fieldname in fields_to_remove:
			df = meta.get("fields", {"fieldname": fieldname})[0]
			if df.get("is_custom_field"):
				frappe.delete_doc("Custom Field", df.name)

	def set_idx_property_setter(self):
		meta = frappe.get_meta(self.doc_type)
		field_order_has_changed = [df.fieldname for df in meta.get("fields")] != \
			[d.fieldname for d in self.get("fields")]

		if field_order_has_changed:
			_idx = []
			for df in sorted(self.get("fields"), key=lambda x: x.idx):
				_idx.append(df.fieldname)

			self.make_property_setter(property="_idx", value=json.dumps(_idx), property_type="Text")

	def make_property_setter(self, property, value, property_type, fieldname=None):
		self.delete_existing_property_setter(property, fieldname)

		property_value = self.get_existing_property_value(property, fieldname)

		if property_value==value:
			return

		# create a new property setter
		# ignore validation becuase it will be done at end
		frappe.make_property_setter({
			"doctype": self.doc_type,
			"doctype_or_field": "DocField" if fieldname else "DocType",
			"fieldname": fieldname,
			"property": property,
			"value": value,
			"property_type": property_type
		}, ignore_validate=True)

	def delete_existing_property_setter(self, property, fieldname=None):
		# first delete existing property setter
		existing_property_setter = frappe.db.get_value("Property Setter", {"doc_type": self.doc_type,
			"property": property, "field_name['']": fieldname or ''})

		if existing_property_setter:
			frappe.delete_doc("Property Setter", existing_property_setter)

	def get_existing_property_value(self, property_name, fieldname=None):
		# check if there is any need to make property setter!
		if fieldname:
			property_value = frappe.db.get_value("DocField", {"parent": self.doc_type,
				"fieldname": fieldname}, property_name)
		else:
			try:
				property_value = frappe.db.get_value("DocType", self.doc_type, property_name)
			except Exception, e:
				if e.args[0]==1054:
					property_value = None
				else:
					raise

		return property_value

	def validate_fieldtype_change(self, df, old_value, new_value):
		allowed = False
		for allowed_changes in allowed_fieldtype_change:
			if (old_value in allowed_changes and new_value in allowed_changes):
				allowed = True
		if not allowed:
			frappe.throw(_("Fieldtype cannot be changed from {0} to {1} in row {2}").format(old_value, new_value, df.idx))

	def reset_to_defaults(self):
		if not self.doc_type:
			return

		frappe.db.sql("""delete from `tabProperty Setter` where doc_type=%s
			and ifnull(field_name, '')!='naming_series'""", self.doc_type)
		frappe.clear_cache(doctype=self.doc_type)
		self.fetch_to_customize()
