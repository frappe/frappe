# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

"""
	Customize Form is a Single DocType used to mask the Property Setter
	Thus providing a better UI from user perspective
"""
import json

import frappe
import frappe.translate
from frappe import _
from frappe.core.doctype.doctype.doctype import (
	check_email_append_to,
	validate_fields_for_doctype,
	validate_series,
)
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.custom.doctype.property_setter.property_setter import delete_property_setter
from frappe.model import core_doctypes_list, no_value_fields
from frappe.model.docfield import supports_translation
from frappe.model.document import Document
from frappe.utils import cint


class CustomizeForm(Document):
	def on_update(self):
		frappe.db.sql("delete from tabSingles where doctype='Customize Form'")
		frappe.db.sql("delete from `tabCustomize Form Field`")

	@frappe.whitelist()
	def fetch_to_customize(self):
		self.clear_existing_doc()
		if not self.doc_type:
			return

		meta = frappe.get_meta(self.doc_type)

		self.validate_doctype(meta)

		# load the meta properties on the customize (self) object
		self.load_properties(meta)

		# load custom translation
		translation = self.get_name_translation()
		self.label = translation.translated_text if translation else ""

		self.create_auto_repeat_custom_field_if_required(meta)

		# NOTE doc (self) is sent to clientside by run_method

	def validate_doctype(self, meta):
		"""
		Check if the doctype is allowed to be customized.
		"""
		if self.doc_type in core_doctypes_list:
			frappe.throw(_("Core DocTypes cannot be customized."))

		if meta.issingle:
			frappe.throw(_("Single DocTypes cannot be customized."))

		if meta.custom:
			frappe.throw(_("Only standard DocTypes are allowed to be customized from Customize Form."))

	def load_properties(self, meta):
		"""
		Load the customize object (this) with the metadata properties
		"""
		# doctype properties
		for prop in doctype_properties:
			self.set(prop, meta.get(prop))

		for d in meta.get("fields"):
			new_d = {"fieldname": d.fieldname, "is_custom_field": d.get("is_custom_field"), "name": d.name}
			for prop in docfield_properties:
				new_d[prop] = d.get(prop)
			self.append("fields", new_d)

		for fieldname in ("links", "actions"):
			for d in meta.get(fieldname):
				self.append(fieldname, d)

	def create_auto_repeat_custom_field_if_required(self, meta):
		"""
		Create auto repeat custom field if it's not already present
		"""
		if self.allow_auto_repeat:
			all_fields = [df.fieldname for df in meta.fields]

			if "auto_repeat" in all_fields:
				return

			insert_after = self.fields[len(self.fields) - 1].fieldname
			create_custom_field(
				self.doc_type,
				dict(
					fieldname="auto_repeat",
					label="Auto Repeat",
					fieldtype="Link",
					options="Auto Repeat",
					insert_after=insert_after,
					read_only=1,
					no_copy=1,
					print_hide=1,
				),
			)

	def get_name_translation(self):
		"""Get translation object if exists of current doctype name in the default language"""
		return frappe.get_value(
			"Translation",
			{"source_text": self.doc_type, "language": frappe.local.lang or "en"},
			["name", "translated_text"],
			as_dict=True,
		)

	def set_name_translation(self):
		"""Create, update custom translation for this doctype"""
		current = self.get_name_translation()
		if not self.label:
			if current:
				# clear translation
				frappe.delete_doc("Translation", current.name)
			return

		if not current:
			frappe.get_doc(
				{
					"doctype": "Translation",
					"source_text": self.doc_type,
					"translated_text": self.label,
					"language_code": frappe.local.lang or "en",
				}
			).insert()
			return

		if self.label != current.translated_text:
			frappe.db.set_value("Translation", current.name, "translated_text", self.label)
			frappe.translate.clear_cache()

	def clear_existing_doc(self):
		doc_type = self.doc_type

		for fieldname in self.meta.get_valid_columns():
			self.set(fieldname, None)

		for df in self.meta.get_table_fields():
			self.set(df.fieldname, [])

		self.doc_type = doc_type
		self.name = "Customize Form"

	@frappe.whitelist()
	def save_customization(self):
		if not self.doc_type:
			return
		validate_series(self, self.autoname, self.doc_type)
		self.flags.update_db = False
		self.flags.rebuild_doctype_for_global_search = False
		self.set_property_setters()
		self.update_custom_fields()
		self.set_name_translation()
		validate_fields_for_doctype(self.doc_type)
		check_email_append_to(self)

		if self.flags.update_db:
			frappe.db.updatedb(self.doc_type)

		if not hasattr(self, "hide_success") or not self.hide_success:
			frappe.msgprint(_("{0} updated").format(_(self.doc_type)), alert=True)
		frappe.clear_cache(doctype=self.doc_type)
		self.fetch_to_customize()

		if self.flags.rebuild_doctype_for_global_search:
			frappe.enqueue(
				"frappe.utils.global_search.rebuild_for_doctype", now=True, doctype=self.doc_type
			)

	def set_property_setters(self):
		meta = frappe.get_meta(self.doc_type)

		# doctype
		self.set_property_setters_for_doctype(meta)

		# docfield
		for df in self.get("fields"):
			meta_df = meta.get("fields", {"fieldname": df.fieldname})
			if not meta_df or meta_df[0].get("is_custom_field"):
				continue
			self.set_property_setters_for_docfield(meta, df, meta_df)

		# action and links
		self.set_property_setters_for_actions_and_links(meta)

	def set_property_setters_for_doctype(self, meta):
		for prop, prop_type in doctype_properties.items():
			if self.get(prop) != meta.get(prop):
				self.make_property_setter(prop, self.get(prop), prop_type)

	def set_property_setters_for_docfield(self, meta, df, meta_df):
		for prop, prop_type in docfield_properties.items():
			if prop != "idx" and (df.get(prop) or "") != (meta_df[0].get(prop) or ""):
				if not self.allow_property_change(prop, meta_df, df):
					continue

				self.make_property_setter(prop, df.get(prop), prop_type, fieldname=df.fieldname)

	def allow_property_change(self, prop, meta_df, df):
		if prop == "fieldtype":
			self.validate_fieldtype_change(df, meta_df[0].get(prop), df.get(prop))

		elif prop == "length":
			old_value_length = cint(meta_df[0].get(prop))
			new_value_length = cint(df.get(prop))

			if new_value_length and (old_value_length > new_value_length):
				self.check_length_for_fieldtypes.append({"df": df, "old_value": meta_df[0].get(prop)})
				self.validate_fieldtype_length()
			else:
				self.flags.update_db = True

		elif prop == "allow_on_submit" and df.get(prop):
			if not frappe.db.get_value(
				"DocField", {"parent": self.doc_type, "fieldname": df.fieldname}, "allow_on_submit"
			):
				frappe.msgprint(
					_("Row {0}: Not allowed to enable Allow on Submit for standard fields").format(df.idx)
				)
				return False

		elif prop == "reqd" and (
			(
				frappe.db.get_value("DocField", {"parent": self.doc_type, "fieldname": df.fieldname}, "reqd")
				== 1
			)
			and (df.get(prop) == 0)
		):
			frappe.msgprint(
				_("Row {0}: Not allowed to disable Mandatory for standard fields").format(df.idx)
			)
			return False

		elif (
			prop == "in_list_view"
			and df.get(prop)
			and df.fieldtype != "Attach Image"
			and df.fieldtype in no_value_fields
		):
			frappe.msgprint(
				_("'In List View' not allowed for type {0} in row {1}").format(df.fieldtype, df.idx)
			)
			return False

		elif (
			prop == "precision"
			and cint(df.get("precision")) > 6
			and cint(df.get("precision")) > cint(meta_df[0].get("precision"))
		):
			self.flags.update_db = True

		elif prop == "unique":
			self.flags.update_db = True

		elif (
			prop == "read_only"
			and cint(df.get("read_only")) == 0
			and frappe.db.get_value(
				"DocField", {"parent": self.doc_type, "fieldname": df.fieldname}, "read_only"
			)
			== 1
		):
			# if docfield has read_only checked and user is trying to make it editable, don't allow it
			frappe.msgprint(_("You cannot unset 'Read Only' for field {0}").format(df.label))
			return False

		elif prop == "options" and df.get("fieldtype") not in ALLOWED_OPTIONS_CHANGE:
			frappe.msgprint(_("You can't set 'Options' for field {0}").format(df.label))
			return False

		elif prop == "translatable" and not supports_translation(df.get("fieldtype")):
			frappe.msgprint(_("You can't set 'Translatable' for field {0}").format(df.label))
			return False

		elif prop == "in_global_search" and df.in_global_search != meta_df[0].get("in_global_search"):
			self.flags.rebuild_doctype_for_global_search = True

		return True

	def set_property_setters_for_actions_and_links(self, meta):
		"""
		Apply property setters or create custom records for DocType Action and DocType Link
		"""
		for doctype, fieldname, field_map in (
			("DocType Link", "links", doctype_link_properties),
			("DocType Action", "actions", doctype_action_properties),
		):
			has_custom = False
			items = []
			for i, d in enumerate(self.get(fieldname) or []):
				d.idx = i
				if frappe.db.exists(doctype, d.name) and not d.custom:
					# check property and apply property setter
					original = frappe.get_doc(doctype, d.name)
					for prop, prop_type in field_map.items():
						if d.get(prop) != original.get(prop):
							self.make_property_setter(prop, d.get(prop), prop_type, apply_on=doctype, row_name=d.name)
					items.append(d.name)
				else:
					# custom - just insert/update
					d.parent = self.doc_type
					d.custom = 1
					d.save(ignore_permissions=True)
					has_custom = True
					items.append(d.name)

			self.update_order_property_setter(has_custom, fieldname)
			self.clear_removed_items(doctype, items)

	def update_order_property_setter(self, has_custom, fieldname):
		"""
		We need to maintain the order of the link/actions if the user has shuffled them.
		So we create a new property (ex `links_order`) to keep a list of items.
		"""
		property_name = "{}_order".format(fieldname)
		if has_custom:
			# save the order of the actions and links
			self.make_property_setter(
				property_name, json.dumps([d.name for d in self.get(fieldname)]), "Small Text"
			)
		else:
			frappe.db.delete("Property Setter", dict(property=property_name, doc_type=self.doc_type))

	def clear_removed_items(self, doctype, items):
		"""
		Clear rows that do not appear in `items`. These have been removed by the user.
		"""
		if items:
			frappe.db.delete(doctype, dict(parent=self.doc_type, custom=1, name=("not in", items)))
		else:
			frappe.db.delete(doctype, dict(parent=self.doc_type, custom=1))

	def update_custom_fields(self):
		for i, df in enumerate(self.get("fields")):
			if df.get("is_custom_field"):
				if not frappe.db.exists("Custom Field", {"dt": self.doc_type, "fieldname": df.fieldname}):
					self.add_custom_field(df, i)
					self.flags.update_db = True
				else:
					self.update_in_custom_field(df, i)

		self.delete_custom_fields()

	def add_custom_field(self, df, i):
		d = frappe.new_doc("Custom Field")

		d.dt = self.doc_type

		for prop in docfield_properties:
			d.set(prop, df.get(prop))

		if i != 0:
			d.insert_after = self.fields[i - 1].fieldname
		d.idx = i

		d.insert()
		df.fieldname = d.fieldname

		if df.get("in_global_search"):
			self.flags.rebuild_doctype_for_global_search = True

	def update_in_custom_field(self, df, i):
		meta = frappe.get_meta(self.doc_type)
		meta_df = meta.get("fields", {"fieldname": df.fieldname})
		if not (meta_df and meta_df[0].get("is_custom_field")):
			# not a custom field
			return

		custom_field = frappe.get_doc("Custom Field", meta_df[0].name)
		changed = False
		for prop in docfield_properties:
			if df.get(prop) != custom_field.get(prop):
				if prop == "fieldtype":
					self.validate_fieldtype_change(df, meta_df[0].get(prop), df.get(prop))
				if prop == "in_global_search":
					self.flags.rebuild_doctype_for_global_search = True

				custom_field.set(prop, df.get(prop))
				changed = True

		# check and update `insert_after` property
		if i != 0:
			insert_after = self.fields[i - 1].fieldname
			if custom_field.insert_after != insert_after:
				custom_field.insert_after = insert_after
				custom_field.idx = i
				changed = True

		if changed:
			custom_field.db_update()
			self.flags.update_db = True
			# custom_field.save()

	def delete_custom_fields(self):
		meta = frappe.get_meta(self.doc_type)
		fields_to_remove = set([df.fieldname for df in meta.get("fields")]) - set(
			df.fieldname for df in self.get("fields")
		)

		for fieldname in fields_to_remove:
			df = meta.get("fields", {"fieldname": fieldname})[0]
			if df.get("is_custom_field"):
				frappe.delete_doc("Custom Field", df.name)

	def make_property_setter(
		self, prop, value, property_type, fieldname=None, apply_on=None, row_name=None
	):
		delete_property_setter(self.doc_type, prop, fieldname, row_name)

		property_value = self.get_existing_property_value(prop, fieldname)

		if property_value == value:
			return

		if not apply_on:
			apply_on = "DocField" if fieldname else "DocType"

		# create a new property setter
		frappe.make_property_setter(
			{
				"doctype": self.doc_type,
				"doctype_or_field": apply_on,
				"fieldname": fieldname,
				"row_name": row_name,
				"property": prop,
				"value": value,
				"property_type": property_type,
			}
		)

	def get_existing_property_value(self, property_name, fieldname=None):
		# check if there is any need to make property setter!
		if fieldname:
			property_value = frappe.db.get_value(
				"DocField", {"parent": self.doc_type, "fieldname": fieldname}, property_name
			)
		else:
			if frappe.db.has_column("DocType", property_name):
				property_value = frappe.db.get_value("DocType", self.doc_type, property_name)
			else:
				property_value = None

		return property_value

	def validate_fieldtype_change(self, df, old_value, new_value):
		allowed = self.allow_fieldtype_change(old_value, new_value)
		if allowed:
			old_value_length = cint(frappe.db.type_map.get(old_value)[1])
			new_value_length = cint(frappe.db.type_map.get(new_value)[1])

			# Ignore fieldtype check validation if new field type has unspecified maxlength
			# Changes like DATA to TEXT, where new_value_lenth equals 0 will not be validated
			if new_value_length and (old_value_length > new_value_length):
				self.check_length_for_fieldtypes.append({"df": df, "old_value": old_value})
				self.validate_fieldtype_length()
			else:
				self.flags.update_db = True
		if not allowed:
			frappe.throw(
				_("Fieldtype cannot be changed from {0} to {1} in row {2}").format(
					old_value, new_value, df.idx
				)
			)

	def validate_fieldtype_length(self):
		for field in self.check_length_for_fieldtypes:
			df = field.get("df")
			max_length = cint(frappe.db.type_map.get(df.fieldtype)[1])
			fieldname = df.fieldname
			docs = frappe.db.sql(
				"""
				SELECT name, {fieldname}, LENGTH({fieldname}) AS len
				FROM `tab{doctype}`
				WHERE LENGTH({fieldname}) > {max_length}
			""".format(
					fieldname=fieldname, doctype=self.doc_type, max_length=max_length
				),
				as_dict=True,
			)
			links = []
			label = df.label
			for doc in docs:
				links.append(frappe.utils.get_link_to_form(self.doc_type, doc.name))
			links_str = ", ".join(links)

			if docs:
				frappe.throw(
					_(
						"Value for field {0} is too long in {1}. Length should be lesser than {2} characters"
					).format(frappe.bold(label), links_str, frappe.bold(max_length)),
					title=_("Data Too Long"),
					is_minimizable=len(docs) > 1,
				)

		self.flags.update_db = True

	@frappe.whitelist()
	def reset_to_defaults(self):
		if not self.doc_type:
			return

		reset_customization(self.doc_type)
		self.fetch_to_customize()

	@classmethod
	def allow_fieldtype_change(self, old_type: str, new_type: str) -> bool:
		"""allow type change, if both old_type and new_type are in same field group.
		field groups are defined in ALLOWED_FIELDTYPE_CHANGE variables.
		"""
		in_field_group = lambda group: (old_type in group) and (new_type in group)
		return any(map(in_field_group, ALLOWED_FIELDTYPE_CHANGE))


def reset_customization(doctype):
	setters = frappe.get_all(
		"Property Setter",
		filters={
			"doc_type": doctype,
			"field_name": ["!=", "naming_series"],
			"property": ["!=", "options"],
		},
		pluck="name",
	)

	for setter in setters:
		frappe.delete_doc("Property Setter", setter)

	frappe.clear_cache(doctype=doctype)


doctype_properties = {
	"search_fields": "Data",
	"title_field": "Data",
	"image_field": "Data",
	"sort_field": "Data",
	"sort_order": "Data",
	"default_print_format": "Data",
	"allow_copy": "Check",
	"istable": "Check",
	"quick_entry": "Check",
	"editable_grid": "Check",
	"max_attachments": "Int",
	"make_attachments_public": "Check",
	"track_changes": "Check",
	"track_views": "Check",
	"allow_auto_repeat": "Check",
	"allow_import": "Check",
	"show_preview_popup": "Check",
	"default_email_template": "Data",
	"email_append_to": "Check",
	"subject_field": "Data",
	"sender_field": "Data",
	"autoname": "Data",
	"translated_doctype": "Check",
}

docfield_properties = {
	"idx": "Int",
	"label": "Data",
	"fieldtype": "Select",
	"options": "Text",
	"fetch_from": "Small Text",
	"fetch_if_empty": "Check",
	"permlevel": "Int",
	"width": "Data",
	"print_width": "Data",
	"non_negative": "Check",
	"reqd": "Check",
	"unique": "Check",
	"ignore_user_permissions": "Check",
	"in_list_view": "Check",
	"in_standard_filter": "Check",
	"in_global_search": "Check",
	"in_preview": "Check",
	"bold": "Check",
	"no_copy": "Check",
	"ignore_xss_filter": "Check",
	"hidden": "Check",
	"collapsible": "Check",
	"collapsible_depends_on": "Data",
	"print_hide": "Check",
	"print_hide_if_no_value": "Check",
	"report_hide": "Check",
	"allow_on_submit": "Check",
	"translatable": "Check",
	"mandatory_depends_on": "Data",
	"read_only_depends_on": "Data",
	"depends_on": "Data",
	"description": "Text",
	"default": "Text",
	"precision": "Select",
	"read_only": "Check",
	"length": "Int",
	"columns": "Int",
	"remember_last_selected_value": "Check",
	"allow_bulk_edit": "Check",
	"auto_repeat": "Link",
	"allow_in_quick_entry": "Check",
	"hide_border": "Check",
	"hide_days": "Check",
	"hide_seconds": "Check",
}

doctype_link_properties = {
	"link_doctype": "Link",
	"link_fieldname": "Data",
	"group": "Data",
	"hidden": "Check",
}

doctype_action_properties = {
	"label": "Link",
	"action_type": "Select",
	"action": "Small Text",
	"group": "Data",
	"hidden": "Check",
}


ALLOWED_FIELDTYPE_CHANGE = (
	("Currency", "Float", "Percent"),
	("Small Text", "Data"),
	("Text", "Data"),
	("Text", "Text Editor", "Code", "Signature", "HTML Editor"),
	("Data", "Select"),
	("Text", "Small Text"),
	("Text", "Data", "Barcode"),
	("Code", "Geolocation"),
	("Table", "Table MultiSelect"),
)

ALLOWED_OPTIONS_CHANGE = ("Read Only", "HTML", "Data")
