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

	parent_doctype = filters.pop('doctype')
	excluded_fieldtypes = ['Column Break']
	excluded_fieldtypes += filters.get('excluded_fieldtypes', [])

	docfields = frappe.get_all(
		doctype,
		fields=["name as value", "label", "fieldtype"],
		filters={'parent': parent_doctype, 'fieldtype': ['not in', excluded_fieldtypes]},
		or_filters=or_filters,
		limit_start=start,
		limit_page_length=page_len,
		as_list=1,
	)
	return docfields
