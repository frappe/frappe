# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""
	Customize Form is a Single DocType used to mask the Property Setter
	Thus providing a better UI from user perspective
"""
import frappe
import frappe.translate
from frappe import _
from frappe.utils import cint
from frappe.model.document import Document
from frappe.model import no_value_fields
from frappe.core.doctype.doctype.doctype import validate_fields_for_doctype

doctype_properties = {
	'search_fields': 'Data',
	'title_field': 'Data',
	'image_field': 'Data',
	'sort_field': 'Data',
	'sort_order': 'Data',
	'default_print_format': 'Data',
	'read_only_onload': 'Check',
	'allow_copy': 'Check',
	'istable': 'Check',
	'quick_entry': 'Check',
	'editable_grid': 'Check',
	'max_attachments': 'Int',
	'image_view': 'Check',
	'track_changes': 'Check',
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
	'in_list_view': 'Check',
	'in_standard_filter': 'Check',
	'in_global_search': 'Check',
	'bold': 'Check',
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
	'length': 'Int',
	'columns': 'Int',
	'remember_last_selected_value': 'Check',
	'allow_bulk_edit': 'Check',
}

allowed_fieldtype_change = (('Currency', 'Float', 'Percent'), ('Small Text', 'Data'),
	('Text', 'Data'), ('Text', 'Text Editor', 'Code', 'Signature'), ('Data', 'Select'),
	('Text', 'Small Text'))

allowed_fieldtype_for_options_change = ('Read Only', 'HTML', 'Select',)

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

		# load custom translation
		translation = self.get_name_translation()
		self.label = translation.target_name if translation else ''

		# NOTE doc is sent to clientside by run_method

	def get_name_translation(self):
		'''Get translation object if exists of current doctype name in the default language'''
		return frappe.get_value('Translation',
			{'source_name': self.doc_type, 'language': frappe.local.lang or 'en'},
			['name', 'target_name'], as_dict=True)

	def set_name_translation(self):
		'''Create, update custom translation for this doctype'''
		current = self.get_name_translation()
		if current:
			if self.label and current!=self.label:
				frappe.db.set_value('Translation', current.name, 'target_name', self.label)
				frappe.translate.clear_cache()
			else:
				# clear translation
				frappe.delete_doc('Translation', current.name)

		else:
			if self.label:
				frappe.get_doc(dict(doctype='Translation',
					source_name=self.doc_type,
					target_name=self.label,
					language_code=frappe.local.lang or 'en')).insert()

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

		self.flags.update_db = False

		self.set_property_setters()
		self.update_custom_fields()
		self.set_name_translation()
		validate_fields_for_doctype(self.doc_type)

		if self.flags.update_db:
			from frappe.model.db_schema import updatedb
			updatedb(self.doc_type)

		if not hasattr(self, 'hide_success') or not self.hide_success:
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
						and df.fieldtype!="Attach Image" and df.fieldtype in no_value_fields:
								frappe.msgprint(_("'In List View' not allowed for type {0} in row {1}")
									.format(df.fieldtype, df.idx))
								continue

					elif property == "precision" and cint(df.get("precision")) > 6 \
							and cint(df.get("precision")) > cint(meta_df[0].get("precision")):
						self.flags.update_db = True

					elif property == "unique":
						self.flags.update_db = True

					elif (property == "read_only" and cint(df.get("read_only"))==0
						and frappe.db.get_value("DocField", {"parent": self.doc_type, "fieldname": df.fieldname}, "read_only")==1):
						# if docfield has read_only checked and user is trying to make it editable, don't allow it
						frappe.msgprint(_("You cannot unset 'Read Only' for field {0}").format(df.label))
						continue

					elif property == "options" and df.get("fieldtype") not in allowed_fieldtype_for_options_change:
						frappe.msgprint(_("You can't set 'Options' for field {0}").format(df.label))
						continue

					self.make_property_setter(property=property, value=df.get(property),
						property_type=docfield_properties[property], fieldname=df.fieldname)

	def update_custom_fields(self):
		for i, df in enumerate(self.get("fields")):
			if df.get("is_custom_field"):
				if not frappe.db.exists('Custom Field', {'dt': self.doc_type, 'fieldname': df.fieldname}):
					self.add_custom_field(df, i)
					self.flags.update_db = True
				else:
					self.update_in_custom_field(df, i)

		self.delete_custom_fields()

	def add_custom_field(self, df, i):
		d = frappe.new_doc("Custom Field")

		d.dt = self.doc_type

		for property in docfield_properties:
			d.set(property, df.get(property))

		if i!=0:
			d.insert_after = self.fields[i-1].fieldname
		d.idx = i

		d.insert()
		df.fieldname = d.fieldname

	def update_in_custom_field(self, df, i):
		meta = frappe.get_meta(self.doc_type)
		meta_df = meta.get("fields", {"fieldname": df.fieldname})
		if not (meta_df and meta_df[0].get("is_custom_field")):
			# not a custom field
			return

		custom_field = frappe.get_doc("Custom Field", meta_df[0].name)
		changed = False
		for property in docfield_properties:
			if df.get(property) != custom_field.get(property):
				if property == "fieldtype":
					self.validate_fieldtype_change(df, meta_df[0].get(property), df.get(property))

				custom_field.set(property, df.get(property))
				changed = True

		# check and update `insert_after` property
		if i!=0:
			insert_after = self.fields[i-1].fieldname
			if custom_field.insert_after != insert_after:
				custom_field.insert_after = insert_after
				custom_field.idx = i
				changed = True

		if changed:
			custom_field.db_update()
			self.flags.update_db = True
			#custom_field.save()

	def delete_custom_fields(self):
		meta = frappe.get_meta(self.doc_type)
		fields_to_remove = (set([df.fieldname for df in meta.get("fields")])
			- set(df.fieldname for df in self.get("fields")))

		for fieldname in fields_to_remove:
			df = meta.get("fields", {"fieldname": fieldname})[0]
			if df.get("is_custom_field"):
				frappe.delete_doc("Custom Field", df.name)

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
			frappe.db.sql("delete from `tabProperty Setter` where name=%s", existing_property_setter)

	def get_existing_property_value(self, property_name, fieldname=None):
		# check if there is any need to make property setter!
		if fieldname:
			property_value = frappe.db.get_value("DocField", {"parent": self.doc_type,
				"fieldname": fieldname}, property_name)
		else:
			try:
				property_value = frappe.db.get_value("DocType", self.doc_type, property_name)
			except Exception as e:
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
				break
		if not allowed:
			frappe.throw(_("Fieldtype cannot be changed from {0} to {1} in row {2}").format(old_value, new_value, df.idx))

	def reset_to_defaults(self):
		if not self.doc_type:
			return

		frappe.db.sql("""delete from `tabProperty Setter` where doc_type=%s
			and ifnull(field_name, '')!='naming_series'""", self.doc_type)
		frappe.clear_cache(doctype=self.doc_type)
		self.fetch_to_customize()
