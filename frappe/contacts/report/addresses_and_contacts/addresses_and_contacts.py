# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE
import frappe
from frappe import _

field_map = {
	"Contact": [
		"first_name",
		"last_name",
		"address",
		"phone",
		"mobile_no",
		"email_id",
		"is_primary_contact",
	],
	"Address": [
		"address_line1",
		"address_line2",
		"city",
		"state",
		"pincode",
		"country",
		"is_primary_address",
	],
}


def execute(filters=None):
	columns, data = get_columns(filters), get_data(filters)
	return columns, data


def get_columns(filters):
	return [
		"{reference_doctype}:Link/{reference_doctype}".format(
			reference_doctype=filters.get("reference_doctype")
		),
		"Address Line 1",
		"Address Line 2",
		"City",
		"State",
		"Postal Code",
		"Country",
		"Is Primary Address:Check",
		"First Name",
		"Last Name",
		"Address",
		"Phone",
		"Email Id",
		"Is Primary Contact:Check",
	]


def get_data(filters):
	reference_doctype = filters.get("reference_doctype")
	reference_name = filters.get("reference_name")

	return get_reference_addresses_and_contact(reference_doctype, reference_name)


def get_reference_addresses_and_contact(reference_doctype, reference_name):
	data = []
	filters = None
	reference_details = frappe._dict()

	if not reference_doctype:
		return []

	if reference_name:
		filters = {"name": reference_name}

	reference_list = [
		d[0] for d in frappe.get_list(reference_doctype, filters=filters, fields=["name"], as_list=True)
	]

	for d in reference_list:
		reference_details.setdefault(d, frappe._dict())
	reference_details = get_reference_details(reference_doctype, "Address", reference_list, reference_details)
	reference_details = get_reference_details(reference_doctype, "Contact", reference_list, reference_details)

	for reference_name, details in reference_details.items():
		addresses = details.get("address", [])
		contacts = details.get("contact", [])
		if not any([addresses, contacts]):
			result = [reference_name]
			result.extend(add_blank_columns_for("Address"))
			result.extend(add_blank_columns_for("Contact"))
			data.append(result)
		else:
			addresses = list(map(list, addresses))
			contacts = list(map(list, contacts))

			max_length = max(len(addresses), len(contacts))
			for idx in range(0, max_length):
				result = [reference_name]

				result.extend(addresses[idx] if idx < len(addresses) else add_blank_columns_for("Address"))
				result.extend(contacts[idx] if idx < len(contacts) else add_blank_columns_for("Contact"))

				data.append(result)

	return data


def get_reference_details(reference_doctype, doctype, reference_list, reference_details):
	filters = [
		["Dynamic Link", "link_doctype", "=", reference_doctype],
		["Dynamic Link", "link_name", "in", reference_list],
	]
	fields = ["`tabDynamic Link`.link_name", *field_map.get(doctype, [])]

	records = frappe.get_list(doctype, filters=filters, fields=fields, as_list=True)
	temp_records = [d[1:] for d in records]

	if not reference_list:
		frappe.throw(_("No records present in {0}").format(reference_doctype))

	reference_details[reference_list[0]][frappe.scrub(doctype)] = temp_records
	return reference_details


def add_blank_columns_for(doctype):
	return ["" for field in field_map.get(doctype, [])]
