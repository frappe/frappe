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


	# end: auto-generated types

	pass

@frappe.whitelist()
def get_config(config_name):
	config = frappe.get_doc("View Config", config_name)

	doctype_fields = get_doctype_fields(config.document_type)
	
	return {
		"columns": frappe.parse_json(config.columns),
		"document_type": config.document_type,
		"label": config.label,
		"doctype_fields": doctype_fields
	}

def get_doctype_fields(doctype):
	meta = frappe.get_meta(doctype)
	not_allowed_in_list_view = get_fields_not_allowed_in_list_view(meta)
	doctype_fields = []
	for field in meta.fields:
		if field.fieldtype in not_allowed_in_list_view:
			continue
		doctype_fields.append({"label": field.label, "value": field.fieldname, "type": field.fieldtype})
	return doctype_fields

@frappe.whitelist()
def update_config(config_name, new_config):
	new_config = frappe._dict(new_config)
	config = frappe.get_doc("View Config", config_name)
	config.columns = json.dumps(frappe.parse_json(new_config.columns))
	config.save()