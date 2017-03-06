# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

@frappe.whitelist()
def get_address_and_contact_list():
	contacts = frappe.db.sql("""select distinct dl.link_name, dl.link_doctype from `tabDynamic Link` as dl
						where dl.link_doctype in ("Customer", "Supplier", "Sales Partner", "Lead")""", as_dict = 1)			
	address_and_contact_list = []
	for contact in contacts:
		address_and_contact = get_address_and_contact(contact.link_doctype, contact.link_name)
		if contact.link_doctype == "Sales Partner":
			title_field = "partner_name"
		else:
			title_field = contact.link_doctype +"_name"		
		address_and_contact_list.append(frappe._dict({
			"title": frappe.get_value(contact.link_doctype, {"name":contact.link_name}, title_field),
			"type": contact.link_doctype,
			"address_list": address_and_contact.address_list,
			"contact_list": address_and_contact.contact_list
		}))
	return address_and_contact_list

def get_address_and_contact(link_doctype, link_name):
	from frappe.geo.doctype.address.address import get_address_display

	address_and_contact_list = []

	filters = [
		["Dynamic Link", "link_doctype", "=", link_doctype],
		["Dynamic Link", "link_name", "=", link_name],
		["Dynamic Link", "parenttype", "=", "Address"],
	]

	address_list = frappe.get_all("Address", filters=filters, fields=['pincode', 'county', 'address_line2', 'city', 'address_line1', 'address_title',
	'state','address_type', 'fax','country','modified'])

	address_list = [a.update({"display": get_address_display(a)})
		for a in address_list]

	contact_list = []
	if link_doctype == "Lead":
		contact_list = frappe.get_all("Lead", filters={"name":link_name}, fields=['email_id','image', 'mobile_no', 'phone',
						'modified'])
	else:					
		filters = [
			["Dynamic Link", "link_doctype", "=", link_doctype],
			["Dynamic Link", "link_name", "=", link_name],
			["Dynamic Link", "parenttype", "=", "Contact"],
		]
		contact_list = frappe.get_all("Contact", filters=filters, fields=['email_id','image', 'mobile_no', 'phone',
						'modified'])					
	address_and_contact_list.append(frappe._dict({
		"address_list": address_list,
		"contact_list": contact_list
	}))
	return address_and_contact_list[0]