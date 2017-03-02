# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	columns, data = get_columns(filters), get_data(filters)
	return columns, data

def get_columns(filters):
	return [
		"Date:Date",
		"Average Rating",
	]

def get_data(filters):
	data = []
	document_type = filters.get("document_type")
	party = filters.get("document_id")
	filters = {
		"reference_doctype": document_type,
		"communication_type": "Feedback",
		"creation": ["Between", [filters.get("from_date"), filters.get("to_date")]]
	}
	fields = ["DATE_FORMAT(DATE(creation),'%m-%d-%Y')", "avg(rating) as rating"]

	if not document_type:
		return []

	if party:
		filters.update({ "reference_name": party })
		
	party_details = frappe.get_list("Communication", filters=filters, fields=fields,
		order_by="creation", group_by="DATE_FORMAT(DATE(creation),'%m-%d-%Y')", as_list=True)

	return party_details or []

@frappe.whitelist()
def get_document_type(doctype, txt, searchfield, start, page_len, filters):
	""" get the document type """

	document_type = []
	txt = "%%%s%%" % txt

	document_type = frappe.get_all("Feedback Trigger", filters={ "enabled": 1, "document_type": ("like", txt) },
		fields=["document_type"], as_list=True)

	document_type = map(list, document_type)
	to_ignore = [ doc[0] for doc in document_type ]

	documents = frappe.get_all("Feedback Request", filters={ "reference_doctype": ["not in", to_ignore] },
		fields=["reference_doctype"], distinct=True, as_list=True)

	if documents:
		document_type.extend(documents)

	return document_type
