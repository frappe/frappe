# Copyright (c) 2021, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class FormTour(Document):
	pass

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_docfield_list(doctype, txt, searchfield, start, page_len, filters):
	or_filters = [
		['fieldname', 'like', '%' + txt + '%'],
		['label', 'like', '%' + txt + '%'],
		['fieldtype', 'like', '%' + txt + '%']
	]

	parent_doctype = filters.get('doctype')
	fieldtype = filters.get('fieldtype')
	if not fieldtype:
		excluded_fieldtypes = ['Column Break']
		excluded_fieldtypes += filters.get('excluded_fieldtypes', [])
		fieldtype_filter = ['not in', excluded_fieldtypes]
	else:
		fieldtype_filter = fieldtype

	docfields = frappe.get_all(
		doctype,
		fields=["name as value", "label", "fieldtype"],
		filters={'parent': parent_doctype, 'fieldtype': fieldtype_filter},
		or_filters=or_filters,
		limit_start=start,
		limit_page_length=page_len,
		order_by="idx",
		as_list=1,
	)
	return docfields
