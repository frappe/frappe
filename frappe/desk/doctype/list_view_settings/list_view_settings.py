# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from six import string_types
from frappe.exceptions import DoesNotExistError
import json

class ListViewSettings(Document):

	def on_update(self):
		frappe.clear_document_cache(self.doctype, self.name)

@frappe.whitelist()
def save_listview_settings(doctype, listview_settings, removed_listview_fields):

	if isinstance(listview_settings, string_types):
		listview_settings = json.loads(listview_settings)

	if isinstance(removed_listview_fields, string_types):
		removed_listview_fields = json.loads(removed_listview_fields)

	try:
		doc = frappe.get_doc("List View Settings", doctype)
		doc.update(listview_settings)
		doc.save()
	except DoesNotExistError:
		doc = frappe.new_doc("List View Settings")
		doc.name = doctype
		doc.update(listview_settings)
		doc.insert()

	set_listview_fields(doctype, listview_settings.get("fields"), removed_listview_fields)

	return {
		"meta": frappe.get_meta(doctype, False),
		"listview_settings": doc
	}

def set_listview_fields(doctype, listview_fields, removed_listview_fields):
	meta = frappe.get_meta(doctype)

	if isinstance(listview_fields, string_types):
		listview_fields = [f.get("fieldname") for f in json.loads(listview_fields)]

	for field in removed_listview_fields:
		set_in_list_view_property(doctype, meta.get_field(field), "0")

	for field in listview_fields:
		set_in_list_view_property(doctype, meta.get_field(field), "1")

def set_in_list_view_property(doctype, field, value):
	property_setter = frappe.db.get_value("Property Setter", {"doc_type": doctype, "field_name": field.fieldname, "property": "in_list_view"})
	if property_setter:
		doc = frappe.get_doc("Property Setter", property_setter)
		doc.value = value
		doc.save()
	else:
		frappe.make_property_setter({
			"doctype": doctype,
			"doctype_or_field": "DocField",
			"fieldname": field.fieldname,
			"property": "in_list_view",
			"value": value,
			"property_type": "Check"
		}, ignore_validate=True)

@frappe.whitelist()
def get_default_listview_fields(doctype):
	meta = frappe.get_meta(doctype)
	path = frappe.get_module_path(frappe.scrub(meta.module), "doctype", frappe.scrub(meta.name), frappe.scrub(meta.name) + ".json")
	json = frappe.get_file_json(path)

	fields = [f.get("fieldname") for f in json.get("fields") if f.get("in_list_view")]

	if meta.title_field:
		if not meta.title_field.strip() in fields:
			fields.append(meta.title_field.strip())

	return fields
