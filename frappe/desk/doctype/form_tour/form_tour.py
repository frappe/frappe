# Copyright (c) 2021, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import slug
from frappe.model.document import Document

class FormTour(Document):
	pass

@frappe.whitelist()
def get_form_tour_steps(tour_name):
	def get_step(step_doc):
		return dict(
			title=step_doc.title,
			condition=step_doc.condition,
			fieldname=step_doc.fieldname,
			description=step_doc.description,
			position=slug(step_doc.position),
		)

	tour = frappe.get_doc('Form Tour', tour_name)
	return [get_step(d) for d in tour.steps]

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def docfields_query(doctype, txt, searchfield, start, page_len, filters):
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