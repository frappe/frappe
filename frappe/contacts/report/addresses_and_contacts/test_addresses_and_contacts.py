import frappe
import frappe.defaults
from frappe.contacts.report.addresses_and_contacts.addresses_and_contacts import get_data
from frappe.tests.utils import FrappeTestCase


def get_custom_linked_doctype():
	if bool(frappe.get_all("DocType", filters={"name": "Test Custom Doctype"})):
		return

	doc = frappe.get_doc(
		{
			"doctype": "DocType",
			"module": "Core",
			"custom": 1,
			"fields": [
				{"label": "Test Field", "fieldname": "test_field", "fieldtype": "Data"},
				{"label": "Contact HTML", "fieldname": "contact_html", "fieldtype": "HTML"},
				{"label": "Address HTML", "fieldname": "address_html", "fieldtype": "HTML"},
			],
			"permissions": [{"role": "System Manager", "read": 1}],
			"name": "Test Custom Doctype",
		}
	)
	doc.insert()


def get_custom_doc_for_address_and_contacts():
	get_custom_linked_doctype()
	linked_doc = frappe.get_doc(
		{
			"doctype": "Test Custom Doctype",
			"test_field": "Hello",
		}
	).insert()
	return linked_doc


def create_linked_address(link_list):
	if frappe.flags.test_address_created:
		return

	address = frappe.get_doc(
		{
			"doctype": "Address",
			"address_title": "_Test Address",
			"address_type": "Billing",
			"address_line1": "test address line 1",
			"address_line2": "test address line 2",
			"city": "Milan",
			"country": "Italy",
		}
	)

	for name in link_list:
		address.append("links", {"link_doctype": "Test Custom Doctype", "link_name": name})

	address.insert()
	frappe.flags.test_address_created = True

	return address.name


def create_linked_contact(link_list, address):
	if frappe.flags.test_contact_created:
		return

	contact = frappe.get_doc(
		{
			"doctype": "Contact",
			"salutation": "Mr",
			"first_name": "_Test First Name",
			"last_name": "_Test Last Name",
			"is_primary_contact": 1,
			"address": address,
			"status": "Open",
		}
	)
	contact.add_email("test_contact@example.com", is_primary=True)
	contact.add_phone("+91 0000000000", is_primary_phone=True)

	for name in link_list:
		contact.append("links", {"link_doctype": "Test Custom Doctype", "link_name": name})

	contact.insert(ignore_permissions=True)
	frappe.flags.test_contact_created = True


class TestAddressesAndContacts(FrappeTestCase):
	def test_get_data(self):
		linked_docs = [get_custom_doc_for_address_and_contacts()]
		links_list = [item.name for item in linked_docs]
		d = create_linked_address(links_list)
		create_linked_contact(links_list, d)
		report_data = get_data({"reference_doctype": "Test Custom Doctype"})
		for idx, link in enumerate(links_list):
			test_item = [
				link,
				"test address line 1",
				"test address line 2",
				"Milan",
				None,
				None,
				"Italy",
				0,
				"_Test First Name",
				"_Test Last Name",
				"_Test Address-Billing",
				"+91 0000000000",
				"",
				"test_contact@example.com",
				1,
			]
			self.assertListEqual(test_item, report_data[idx])
