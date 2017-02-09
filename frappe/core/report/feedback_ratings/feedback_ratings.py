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
	party_type = filters.get("party_type")
	party = filters.get("party_name")
	filters = {
		"reference_doctype": party_type,
		"communication_type": "Feedback",
		"creation": ["Between", [filters.get("from_date"), filters.get("to_date")]]
	}
	fields = ["DATE_FORMAT(DATE(creation),'%m-%d-%Y')", "avg(rating) as rating"]

	if not party_type:
		return []

	if party:
		filters.update({ "reference_name": party })
		
	party_details = frappe.get_list("Communication", filters=filters, fields=fields,
		order_by="creation", group_by="DATE_FORMAT(DATE(creation),'%m-%d-%Y')", as_list=True)

	return party_details or []
