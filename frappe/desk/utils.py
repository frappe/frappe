# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe

@frappe.whitelist(allow_guest=True)
def get_doctype_name(name):
	# translates the doctype name from url to name `sales-order` to `Sales Order`
	# also supports document type layouts
	# if with_layout is set: return the layout object too

	def get_name_map():
		name_map = {}
		for d in frappe.get_all('DocType'):
			name_map[get_doctype_route(d.name)] = frappe._dict(doctype = d.name)

		for d in frappe.get_all('DocType Layout', fields = ['name', 'document_type']):
			name_map[get_doctype_route(d.name)] = frappe._dict(doctype = d.document_type, doctype_layout = d.name)

		return name_map

	data = frappe._dict(name_map = frappe.cache().get_value('doctype_name_map', get_name_map).get(name, dict(doctype = name)))

	if data.name_map.get('doctype_layout'):
		# return the layout object
		frappe.response.docs.append(frappe.get_doc('DocType Layout', data.name_map.get('doctype_layout')).as_dict())

	return data

def get_doctype_route(name):
	return name.lower().replace(' ', '-')