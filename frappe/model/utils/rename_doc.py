# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from itertools import product

import frappe
from frappe.model.rename_doc import get_link_fields


def update_linked_doctypes(
	doctype: str, docname: str, linked_to: str, value: str, ignore_doctypes: list | None = None
):
	"""
	linked_doctype_info_list = list formed by get_fetch_fields() function
	docname = Master DocType's name in which modification are made
	value = Value for the field thats set in other DocType's by fetching from Master DocType
	"""
	linked_doctype_info_list = get_fetch_fields(doctype, linked_to, ignore_doctypes)

	for d in linked_doctype_info_list:
		frappe.db.set_value(
			d.doctype,
			{
				d.master_fieldname: docname,
				d.linked_to_fieldname: ("!=", value),
			},
			d.linked_to_fieldname,
			value,
		)


def get_fetch_fields(
	doctype: str, linked_to: str, ignore_doctypes: list | None = None
) -> list[dict]:
	"""
	doctype = Master DocType in which the changes are being made
	linked_to = DocType name of the field thats being updated in Master
	This function fetches list of all DocType where both doctype and linked_to is found
	as link fields.
	Forms a list of dict in the form -
	        [{doctype: , master_fieldname: , linked_to_fieldname: ]
	where
	        doctype = DocType where changes need to be made
	        master_fieldname = Fieldname where options = doctype
	        linked_to_fieldname = Fieldname where options = linked_to
	"""

	out = []
	master_list = get_link_fields(doctype)
	linked_to_list = get_link_fields(linked_to)
	product_list = product(master_list, linked_to_list)

	for d in product_list:
		linked_doctype_info = frappe._dict()
		if (
			d[0]["parent"] == d[1]["parent"]
			and (not ignore_doctypes or d[0]["parent"] not in ignore_doctypes)
			and not d[1]["issingle"]
		):
			linked_doctype_info.doctype = d[0]["parent"]
			linked_doctype_info.master_fieldname = d[0]["fieldname"]
			linked_doctype_info.linked_to_fieldname = d[1]["fieldname"]
			out.append(linked_doctype_info)

	return out
