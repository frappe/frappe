# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
from frappe.exceptions import ValidationError

class TestContact(unittest.TestCase):

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

	def test_primary_and_billing(self):
		test_contacts = [
			{"first_name": "Jane", "salutation": "Ms", "is_primary_contact": 0, "is_billing_contact": 1},
			{"first_name": "Joe", "salutation": "Mr", "is_primary_contact": 1, "is_billing_contact": 1},
			{"first_name": "Jason", "salutation": "Dr", "is_primary_contact": 1, "is_billing_contact": 0}
		]
		for contact in test_contacts:
			doc_contact = create_contact(contact.get("first_name"), contact.get("salutation"))
			doc_contact.is_primary_contact = contact.get("is_primary_contact")
			doc_contact.is_billing_contact = contact.get("is_billing_contact")
			doc_contact.save()
			self.assertEqual(doc_contact.is_primary_contact, contact.get("is_primary_contact"))
			self.assertEqual(doc_contact.is_billing_contact, contact.get("is_billing_contact"))

def create_contact(name, salutation, emails=None, phones=None, save=True):
	doc = frappe.get_doc({
			"doctype": "Contact",
			"first_name": name,
			"status": "Open",
			"salutation": salutation
		})

	if emails:
		for d in emails:
			doc.add_email(d.get("email"), d.get("is_primary"))

	if phones:
		for d in phones:
			doc.add_phone(d.get("phone"), d.get("is_primary_phone"), d.get("is_primary_mobile_no"))

	if save:
		doc.insert()

	return doc