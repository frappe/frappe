# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe


party_type_fields = {
	"Customer": ["name", "customer_name", "customer_group"],
	"Supplier": ["name", "supplier_name", "supplier_type"],
	"Contact": [ "first_name", "last_name", "phone", "mobile_no", "email_id", "is_primary_contact" ],
	"Address": [ "address_line1", "address_line2", "city", "state", "pincode", "country", "is_primary_address" ]
}

party_type_columns = {
	"Customer": [
		"Customer ID:Link/Customer",
		"Customer Name",
		"Customer Group:Link/Customer Group",
	],
	"Supplier": [
		"Supplier:Link/Supplier",
		"Supplier Name",
		"Supplier Type:Link/Supplier Type",
	]
}

def execute(filters=None):
	columns, data = get_columns(filters), get_data(filters)
	return columns, data

def get_columns(filters):
	party_type = filters.get("party_type")
	party_columns = party_type_columns.get(party_type)
	address_contact_columns = [
		"Address Line 1",
		"Address Line 2",
		"City",
		"State",
		"Postal Code",
		"Country",
		"Is Primary Address:Check",
		"First Name",
		"Last Name",
		"Phone",
		"Mobile No",
		"Email Id",
		"Is Primary Contact:Check"
	]

	return party_columns + address_contact_columns

def get_data(filters):
	data = []
	party_type = filters.get("party_type")
	party = filters.get("party_name")

	return get_party_addresses_and_contact(party_type, party)

def get_party_addresses_and_contact(party_type, party):
	data = []
	filters = None
	party_details = []
	fields = party_type_fields.get(party_type, "name")

	if not party_type:
		return []

	if party:
		filters = { "name": party }
		
	party_details = frappe.get_list(party_type, filters=filters, fields=fields, as_list=True)
	for party_detail in map(list, party_details):
		docname = party_detail[0]

		addresses = get_party_details(party_type, docname, doctype="Address")
		contacts = get_party_details(party_type, docname, doctype="Contact")

		if not all([addresses, contacts]):
			party_detail.extend([ "" for field in party_type_fields.get("Address", []) ])
			party_detail.extend([ "" for field in party_type_fields.get("Contact", []) ])
			data.append(party_detail)
		else:
			addresses = map(list, addresses)
			contacts = map(list, contacts)

			max_length = max(len(addresses), len(contacts))
			for idx in xrange(0, max_length):
				result = list(party_detail)

				address = addresses[idx] if idx < len(addresses) else [ "" for field in party_type_fields.get("Address", []) ]
				contact = contacts[idx] if idx < len(contacts) else [ "" for field in party_type_fields.get("Contact", []) ]
				result.extend(address)
				result.extend(contact)

				data.append(result)
	return data

def get_party_details(party_type, docname, doctype="Address", fields=None):
	default_filters = get_default_address_contact_filters(party_type, docname)
	if not fields:
		fields = party_type_fields.get(doctype, ["name"])
	return frappe.get_list(doctype, filters=default_filters, fields=fields, as_list=True)

def get_default_address_contact_filters(party_type, docname):
	return [
		["Dynamic Link", "link_doctype", "=", party_type],
		["Dynamic Link", "link_name", "=", docname]
	]