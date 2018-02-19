# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.rename_doc import get_link_fields

def update_linked_doctypes(parent, child, docname, value):
    """
        parent = Master DocType in which the changes are being made
        child = DocType name of the field thats being updated
        name = docname
        value = updated value of the field
    """
    parent_list = get_link_fields(parent)
    child_list = get_link_fields(child)

    product_list = list_combinatrix(parent_list, child_list)

    for d in product_list:
        update_doc_query(d['parent']['parent'], d['child']['fieldname'],
            value, d['parent']['fieldname'], docname)

def get_linked_data_fields(doctype, fieldname):
	# get linked data fields from tabDocField
	data_fields = frappe.db.sql("""\
		select parent, fieldname, options,
			(select issingle from tabDocType dt
			where dt.name = df.parent) as issingle
		from tabDocField df
		where
			df.options like '%%{0}.%%'
			and df.fieldtype='Data'
			and df.parent='{1}'""".format(fieldname, doctype), as_dict=1)

	# get linked data fields from tabCustom Field
	custom_data_fields = frappe.db.sql("""\
		select dt as parent, fieldname, options,
			(select issingle from tabDocType dt
			where dt.name = df.dt) as issingle
		from `tabCustom Field` df
		where
			df.options like '%%{0}.%%'
			and df.fieldtype='Data'
			and df.dt='{1}'""".format(fieldname, doctype), as_dict=1)

	# add custom linked data fields list to linked data fields list
	data_fields += custom_data_fields

	return data_fields

def get_from_add_fetch(for_doctype, from_doctype):
	out = frappe.db.sql("""
		select for_doctype, for_fieldname,
			from_doctype, from_fieldname
		from `tabAdd Fetch`
		where
			for_doctype = '{0}'
			and from_doctype = '{1}'
		""".format(for_doctype, from_doctype), as_dict=1)

	return out


def update_all_values(doc, method):
	"""
		Called through a hook whenever a document is updated.
	"""

	if frappe.local.flags.current_doctype\
		and doc.doctype==frappe.local.flags.current_doctype.get('doctype')\
		and not frappe.local.flags.current_doctype.get('islocal'):

		link_fields = get_link_fields(doc.doctype)

		for d in link_fields:
			data_fields = get_linked_data_fields(d.parent, d.fieldname)
			add_fetch_fields = get_from_add_fetch(d.parent, doc.doctype)

			for k in data_fields:
				fetch_field = k.options.split('.')[1]
				update_doc_query(k.parent, k.fieldname, doc.get(fetch_field),
					d.fieldname, doc.name)

			for k in add_fetch_fields:
				frappe.errprint(k)
				update_doc_query(k.for_doctype, k.for_fieldname, doc.get(k.from_fieldname),
					d.fieldname, doc.name)

def update_doc_query(doctype, fieldname, value, parent_fieldname, docname, condition=""):
	"""
		Updates values of field which depends on some other link field
		in the DocType and mentioned through options.
	"""

	frappe.db.sql("""
		update
			`tab{doctype}`
		set
			{fieldname} = "{value}"
		where
			{parent_fieldname} = "{docname}"
			and {fieldname} != "{value}"
            {condition}
	""".format(
		doctype = doctype,
		fieldname = fieldname,
		value = value,
		parent_fieldname = parent_fieldname,
		docname = docname,
        condition=condition
	))

def list_combinatrix(list1, list2):
	""" form all possible products with the given lists elements """
	out, temp_dict = [], {}

	from itertools import product
	prod = product(list1, list2)

	for d in prod:
		if d[0]['parent'] == d[1]['parent']:
			temp_dict['parent'] = d[0]
			temp_dict['child'] = d[1]
			out.append(temp_dict)
			temp_dict = {}

	return out
