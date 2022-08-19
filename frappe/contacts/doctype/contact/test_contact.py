# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.tests.utils import FrappeTestCase

test_dependencies = ["Contact", "Salutation"]


class TestContact(FrappeTestCase):
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
			{"phone": "+91 0000000000", "is_primary_phone": 0, "is_primary_mobile_no": 0},
			{"phone": "+91 0000000001", "is_primary_phone": 0, "is_primary_mobile_no": 0},
			{"phone": "+91 0000000002", "is_primary_phone": 1, "is_primary_mobile_no": 0},
			{"phone": "+91 0000000003", "is_primary_phone": 0, "is_primary_mobile_no": 1},
		]
		contact = create_contact("Phone", "Mr", phones=phones)

		self.assertEqual(contact.phone, "+91 0000000002")
		self.assertEqual(contact.mobile_no, "+91 0000000003")


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
