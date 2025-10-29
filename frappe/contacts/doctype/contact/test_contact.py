# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.contacts.doctype.contact.contact import get_full_name
from frappe.email import get_contact_list
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = ["Contact", "Salutation"]


class TestContact(IntegrationTestCase):
	def test_check_default_email(self):
		emails = [
			{"email": "test1@example.com", "is_primary": 0},
			{"email": "test2@example.com", "is_primary": 0},
			{"email": "test3@example.com", "is_primary": 0},
			{"email": "test4@example.com", "is_primary": 1},
			{"email": "test5@example.com", "is_primary": 0},
		]
		contact = create_contact("Email", "Mr", emails=emails)

		self.assertEqual(contact.email_id, "test4@example.com")

	def test_check_default_phone_and_mobile(self):
		phones = [
			{"phone": "+91 0000000010", "is_primary_phone": 0, "is_primary_mobile_no": 0},
			{"phone": "+91 0000000011", "is_primary_phone": 0, "is_primary_mobile_no": 0},
			{"phone": "+91 0000000012", "is_primary_phone": 1, "is_primary_mobile_no": 0},
			{"phone": "+91 0000000013", "is_primary_phone": 0, "is_primary_mobile_no": 1},
		]
		contact = create_contact("Phone", "Mr", phones=phones)

		self.assertEqual(contact.phone, "+91 0000000012")
		self.assertEqual(contact.mobile_no, "+91 0000000013")

	def test_get_full_name(self):
		self.assertEqual(get_full_name(first="John"), "John")
		self.assertEqual(get_full_name(last="Doe"), "Doe")
		self.assertEqual(get_full_name(company="Doe Pvt Ltd"), "Doe Pvt Ltd")
		self.assertEqual(get_full_name(first="John", last="Doe"), "John Doe")
		self.assertEqual(get_full_name(first="John", middle="Jane"), "John Jane")
		self.assertEqual(get_full_name(first="John", last="Doe", company="Doe Pvt Ltd"), "John Doe")
		self.assertEqual(
			get_full_name(first="John", middle="Jane", last="Doe", company="Doe Pvt Ltd"),
			"John Jane Doe",
		)

	def test_get_contact_list(self):
		# First time from database
		results = get_contact_list("_Test Supplier")
		self.assertEqual(results[0].label, "test_contact@example.com")
		self.assertEqual(results[0].value, "test_contact@example.com")
		self.assertEqual(results[0].description, "_Test Contact For _Test Supplier")

		# Second time from cache
		results = get_contact_list("_Test Supplier")
		self.assertEqual(results[0].label, "test_contact@example.com")
		self.assertEqual(results[0].value, "test_contact@example.com")
		self.assertEqual(results[0].description, "_Test Contact For _Test Supplier")


def create_contact(name, salutation, emails=None, phones=None, save=True):
	doc = frappe.get_doc(
		{"doctype": "Contact", "first_name": name, "status": "Open", "salutation": salutation}
	)

	if emails:
		for d in emails:
			doc.add_email(d.get("email"), d.get("is_primary"))

	if phones:
		for d in phones:
			doc.add_phone(d.get("phone"), d.get("is_primary_phone"), d.get("is_primary_mobile_no"))

	if save:
		doc.insert()

	return doc
