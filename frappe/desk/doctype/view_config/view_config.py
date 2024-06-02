# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.core.doctype.doctype.doctype import get_fields_not_allowed_in_list_view
import json

class ViewConfig(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		columns: DF.JSON | None
		document_type: DF.Link | None
		filters: DF.JSON | None
		label: DF.Data | None
		sort_field: DF.Data | None
		sort_order: DF.Literal["ASC", "DESC"]
	# end: auto-generated types

	pass

def get_default_config(doctype):
	meta = frappe.get_meta(doctype)
	columns = []
	for field in meta.fields:
		if field.in_list_view:
			columns.append(get_column_dict(field))

	if f := meta.get_field(meta.sort_field):
		if not f.in_list_view:
			columns.append(get_column_dict(f))
	else:
		for f in frappe.model.std_fields:
			f = frappe._dict(f)
			if f.fieldname == meta.sort_field:
				columns.append(get_column_dict(f))
				break
	return {
		"label": "List View",
		"columns": columns,
		"doctype_fields": get_doctype_fields(doctype),
		"filters": [],
		"sort_field": meta.sort_field,
		"sort_order": meta.sort_order
	}

@frappe.whitelist()
def get_config(config_name=None, is_default=True):
	if is_default:
		return get_default_config(config_name)
	config = frappe.get_doc("View Config", config_name)
	
	config_dict = config.as_dict()
	config_dict.update({
		"columns": frappe.parse_json(config.columns),
		"doctype_fields": get_doctype_fields(config.document_type),
		"filters": frappe.parse_json(config.filters),
	})
	return config_dict

def get_doctype_fields(doctype):
	meta = frappe.get_meta(doctype)
	not_allowed_in_list_view = get_fields_not_allowed_in_list_view(meta)
	doctype_fields = []
	for field in meta.fields + frappe.model.std_fields:
		if field.get("fieldtype") in not_allowed_in_list_view:
			continue
		doctype_fields.append({"label": field.get("label"), "value": field.get("fieldname"), "type": field.get("fieldtype"), "options": field.get("options")})
	return doctype_fields

def get_column_dict(field):
	return {
		"label": field.label, 
		"key": field.fieldname, 
		"type": field.fieldtype, 
		"options": field.options, 
		"width": "10rem"
	}

@frappe.whitelist()
def update_config(config_name, new_config):
	new_config = frappe._dict(new_config)
	config = frappe.get_doc("View Config", config_name)
	config.columns = json.dumps(frappe.parse_json(new_config.columns))
	config.filters = json.dumps(frappe.parse_json(new_config.filters))
	config.save()


@frappe.whitelist()
def get_views_for_doctype(doctype):
	return frappe.get_all("View Config", filters={"document_type": doctype}, fields=["name", "label", "icon"])

@frappe.whitelist()
def get_link_title_field(doctype, name):
	meta = frappe.get_meta(doctype)
	if not meta.show_title_field_in_link:
		return name
	return frappe.get_value(doctype, name, meta.title_field) or name
