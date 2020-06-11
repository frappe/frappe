# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class ListViewSettings(Document):

	def on_update(self):
		frappe.clear_document_cache(self.doctype, self.name)

@frappe.whitelist()
def save_listview_settings(doctype, listview_settings, removed_listview_attr):

	listview_settings = frappe.parse_json(listview_settings)
	removed_listview_attr = frappe.parse_json(removed_listview_attr)

	removed_listview_fields = frappe.parse_json(removed_listview_attr.get("removed_listview_fields"))
	removed_listview_filters = frappe.parse_json(removed_listview_attr.get("removed_listview_filters"))

	if frappe.get_all("List View Settings", filters={"name": doctype}):
		doc = frappe.get_doc("List View Settings", doctype)
		doc.update(listview_settings)
		doc.save()
	else:
		doc = frappe.new_doc("List View Settings")
		doc.name = doctype
		doc.update(listview_settings)
		doc.insert()

	set_listview_fields(doctype, listview_settings.get("fields"), removed_listview_fields)
	set_listview_filters(listview_settings.get("filters"), removed_listview_filters)

	return {
		"meta": frappe.get_meta(doctype, False),
		"listview_settings": doc
	}

def set_listview_fields(doctype, listview_fields, removed_listview_fields):
	meta = frappe.get_meta(doctype)

	for field in frappe.parse_json(listview_fields):
		set_property(doctype, meta.get_field(field.get("fieldname")), "in_list_view", "1")

	for field in frappe.parse_json(removed_listview_fields):
		set_property(doctype, meta.get_field(field), "in_list_view", "0")

def set_listview_filters(listview_filters, removed_listview_filters):

	for flt in frappe.parse_json(listview_filters):
		meta = frappe.get_meta(flt.get("doctype"))
		set_property(meta.name, meta.get_field(flt.get("fieldname")), "in_standard_filter", "1")

	for flt in frappe.parse_json(removed_listview_filters):
		meta = frappe.get_meta(flt.get("doctype"))
		set_property(meta.name, meta.get_field(flt.get("fieldname")), "in_standard_filter", "0")


def set_property(doctype, field, property, value):
	if not field or field.fieldname == "status_field":
		return

	property_setter = frappe.db.get_value("Property Setter", {"doc_type": doctype, "field_name": field.fieldname, "property": property})
	if property_setter:
		doc = frappe.get_doc("Property Setter", property_setter)
		doc.value = value
		doc.save()
	else:
		frappe.make_property_setter({
			"doctype": doctype,
			"doctype_or_field": "DocField",
			"fieldname": field.fieldname,
			"property": property,
			"value": value,
			"property_type": "Check"
		}, ignore_validate=True)

@frappe.whitelist()
def get_default_listview_fields(doctype):
	meta = frappe.get_meta(doctype)
	path = frappe.get_module_path(frappe.scrub(meta.module), "doctype", frappe.scrub(meta.name), frappe.scrub(meta.name) + ".json")
	doctype_json = frappe.get_file_json(path)

	fields = [f.get("fieldname") for f in doctype_json.get("fields") if f.get("in_list_view")]

	if meta.title_field:
		if not meta.title_field.strip() in fields:
			fields.append(meta.title_field.strip())

	return {
		doctype: fields
	}

@frappe.whitelist()
def get_default_listview_filters(doctype):
	meta = frappe.get_meta(doctype)
	table_fields = meta.get_table_fields()

	fields = {}

	for meta in [meta] + table_fields:
		if meta.doctype == "DocField":
			meta = frappe.get_meta(meta.options)

		path = frappe.get_module_path(frappe.scrub(meta.module), "doctype", frappe.scrub(meta.name),
			frappe.scrub(meta.name) + ".json")
		doctype_json = frappe.get_file_json(path)

		fields[meta.name] = [f.get("fieldname") for f in doctype_json.get("fields") if f.get("in_standard_filter")]

	return fields
