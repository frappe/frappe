# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from six.moves import range
import frappe


field_map = {
	"Contact": [ "first_name", "last_name", "phone", "mobile_no", "email_id", "is_primary_contact" ],
	"Address": [ "address_line1", "address_line2", "city", "state", "pincode", "country", "is_primary_address" ]
}

def execute(filters=None):
	columns, data = get_columns(filters), get_data(filters)
	return columns, data

def get_columns(filters):
	return [
		"{party_type}:Link/{party_type}".format(party_type=filters.get("party_type")),
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

def get_data(filters):
	data = []
	party_type = filters.get("party_type")
	party = filters.get("party_name")

	return get_party_addresses_and_contact(party_type, party)

def get_party_addresses_and_contact(party_type, party):
	data = []
	filters = None
	party_details = []

	if not party_type:
		return []

	if party:
		filters = { "name": party }
		
	party_details = frappe.get_list(party_type, filters=filters, fields=["name"], as_list=True)
	for party_detail in map(list, party_details):
		docname = party_detail[0]

		addresses = get_party_details(party_type, docname, doctype="Address")
		contacts = get_party_details(party_type, docname, doctype="Contact")

		if not any([addresses, contacts]):
			party_detail.extend([ "" for field in field_map.get("Address", []) ])
			party_detail.extend([ "" for field in field_map.get("Contact", []) ])
			data.append(party_detail)
		else:
			addresses = map(list, addresses)
			contacts = map(list, contacts)

			max_length = max(len(addresses), len(contacts))
			for idx in range(0, max_length):
				result = list(party_detail)

				address = addresses[idx] if idx < len(addresses) else [ "" for field in field_map.get("Address", []) ]
				contact = contacts[idx] if idx < len(contacts) else [ "" for field in field_map.get("Contact", []) ]
				result.extend(address)
				result.extend(contact)

				data.append(result)
	return data

def get_party_details(party_type, docname, doctype="Address", fields=None):
	default_filters = get_default_address_contact_filters(party_type, docname)
	if not fields:
		fields = field_map.get(doctype, ["name"])
	return frappe.get_list(doctype, filters=default_filters, fields=fields, as_list=True)

def get_default_address_contact_filters(party_type, docname):
	return [
		["Dynamic Link", "link_doctype", "=", party_type],
		["Dynamic Link", "link_name", "=", docname]
	]