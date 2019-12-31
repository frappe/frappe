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
			{"phone": "+91 0000000000", "type": "Skype", "is_primary": 1},
			{"phone": "+91 0000000001", "type": "Fax", "is_primary": 1},
			{"phone": "+91 0000000002", "type": "Phone", "is_primary": 1},
			{"phone": "+91 0000000003", "type": "Mobile No", "is_primary": 1},
		]
		contact = create_contact("Phone", "Mr", phones=phones)

		self.assertEqual(contact.skype, "+91 0000000000")
		self.assertEqual(contact.fax, "+91 0000000001")
		self.assertEqual(contact.phone, "+91 0000000002")
		self.assertEqual(contact.mobile_no, "+91 0000000003")

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
			doc.add_phone(d.get("phone"), d.get("type"), d.get("is_primary"))

	if save:
		doc.insert()

	return doc