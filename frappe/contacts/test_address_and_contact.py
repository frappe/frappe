# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.contacts.address_and_contact import remove_link
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.tests import IntegrationTestCase

PRIMARY_FIELDS = {
	"ToDo": [
		{
			"fieldname": "primary_address",
			"label": "Primary Address",
			"fieldtype": "Link",
			"options": "Address",
		},
		{
			"fieldname": "primary_city",
			"label": "Primary City",
			"fieldtype": "Data",
			"fetch_from": "primary_address.city",
		},
	]
}


class TestRemoveLink(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_custom_fields(PRIMARY_FIELDS)
		cls.addClassCleanup(cls.drop_primary_fields)

	@staticmethod
	def drop_primary_fields():
		for field in PRIMARY_FIELDS["ToDo"]:
			frappe.delete_doc("Custom Field", f"ToDo-{field['fieldname']}", force=True)
		frappe.clear_cache(doctype="ToDo")

	def setUp(self):
		self.document = frappe.get_doc({"doctype": "ToDo", "description": "_Test Remove Link"}).insert()
		self.other_document = frappe.get_doc(
			{"doctype": "ToDo", "description": "_Test Remove Link Other"}
		).insert()

	def create_address(self, links):
		return frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "_Test Delink Address",
				"address_type": "Billing",
				"address_line1": "_Test Address Line 1",
				"city": "_Test City",
				"country": "India",
				"links": links,
			}
		).insert()

	def link_to(self, doc):
		return {"link_doctype": doc.doctype, "link_name": doc.name}

	def test_removes_only_the_given_document(self):
		address = self.create_address([self.link_to(self.document), self.link_to(self.other_document)])

		remove_link("Address", address.name, self.document.doctype, self.document.name)

		address.reload()
		self.assertEqual(
			[(link.link_doctype, link.link_name) for link in address.links],
			[(self.other_document.doctype, self.other_document.name)],
		)

	def test_keeps_the_address_itself(self):
		address = self.create_address([self.link_to(self.document)])

		remove_link("Address", address.name, self.document.doctype, self.document.name)

		self.assertTrue(frappe.db.exists("Address", address.name))
		self.assertEqual(frappe.get_doc("Address", address.name).links, [])

	def test_unknown_document_is_a_no_op(self):
		address = self.create_address([self.link_to(self.document)])
		modified_before = frappe.db.get_value("Address", address.name, "modified")

		remove_link("Address", address.name, self.other_document.doctype, self.other_document.name)

		address.reload()
		self.assertEqual(len(address.links), 1)
		self.assertEqual(frappe.db.get_value("Address", address.name, "modified"), modified_before)

	def test_clears_the_documents_primary_link(self):
		address = self.create_address([self.link_to(self.document)])
		self.document.db_set({"primary_address": address.name, "primary_city": "_Test City"})

		remove_link("Address", address.name, self.document.doctype, self.document.name)

		self.document.reload()
		self.assertIsNone(self.document.primary_address)
		self.assertIsNone(self.document.primary_city)

	def test_keeps_a_primary_link_to_another_record(self):
		address = self.create_address([self.link_to(self.document)])
		other_address = self.create_address([self.link_to(self.document)])
		self.document.db_set("primary_address", other_address.name)

		remove_link("Address", address.name, self.document.doctype, self.document.name)

		self.document.reload()
		self.assertEqual(self.document.primary_address, other_address.name)

	def test_rejects_other_doctypes(self):
		with self.assertRaises(frappe.ValidationError):
			remove_link("ToDo", self.document.name, self.document.doctype, self.document.name)
