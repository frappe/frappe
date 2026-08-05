# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.contacts.address_and_contact import delink_party
from frappe.tests import IntegrationTestCase


class TestDelinkParty(IntegrationTestCase):
	def setUp(self):
		self.party = frappe.get_doc({"doctype": "ToDo", "description": "_Test Delink Party"}).insert()
		self.other_party = frappe.get_doc(
			{"doctype": "ToDo", "description": "_Test Delink Other Party"}
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

	def test_removes_only_the_given_party(self):
		address = self.create_address([self.link_to(self.party), self.link_to(self.other_party)])

		delink_party("Address", address.name, self.party.doctype, self.party.name)

		address.reload()
		self.assertEqual(
			[(link.link_doctype, link.link_name) for link in address.links],
			[(self.other_party.doctype, self.other_party.name)],
		)

	def test_keeps_the_address_itself(self):
		address = self.create_address([self.link_to(self.party)])

		delink_party("Address", address.name, self.party.doctype, self.party.name)

		self.assertTrue(frappe.db.exists("Address", address.name))
		self.assertEqual(frappe.get_doc("Address", address.name).links, [])

	def test_unknown_party_is_a_no_op(self):
		address = self.create_address([self.link_to(self.party)])
		modified_before = frappe.db.get_value("Address", address.name, "modified")

		delink_party("Address", address.name, self.other_party.doctype, self.other_party.name)

		address.reload()
		self.assertEqual(len(address.links), 1)
		self.assertEqual(frappe.db.get_value("Address", address.name, "modified"), modified_before)

	def test_rejects_other_doctypes(self):
		with self.assertRaises(frappe.ValidationError):
			delink_party("ToDo", self.party.name, self.party.doctype, self.party.name)
