# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
import json
from frappe.website.doctype.personal_data_download_request.personal_data_download_request import get_user_data
from frappe.contacts.doctype.contact.contact import get_contact_name

class TestRequestPersonalData(unittest.TestCase):
	def setUp(self):
		create_user_if_not_exists(email='test_privacy@example.com')

	def tearDown(self):
		frappe.db.sql("""DELETE FROM `tabPersonal Data Download Request`""")

	def test_user_data_creation(self):
		user_data = json.loads(get_user_data('test_privacy@example.com'))
		contact_name = get_contact_name('test_privacy@example.com')
		expected_data = {'Contact': frappe.get_all('Contact', {"name": contact_name}, ["*"])}
		expected_data = json.loads(json.dumps(expected_data, default=str))
		self.assertEqual({'Contact': user_data['Contact']}, expected_data)

	def test_file_and_email_creation(self):
		frappe.set_user('test_privacy@example.com')
		download_request = frappe.get_doc({
			"doctype": 'Personal Data Download Request',
			'user': 'test_privacy@example.com'
		})
		download_request.save(ignore_permissions=True)

		frappe.set_user('Administrator')

		file_count = frappe.db.count('File', {
			'attached_to_doctype':'Personal Data Download Request',
			'attached_to_name': download_request.name
		})

		self.assertEqual(file_count, 1)

		email_queue = frappe.get_all('Email Queue',
			fields=['message'],
			order_by="creation DESC",
			limit=1)
		self.assertTrue("Subject: Download Your Data" in email_queue[0].message)

		frappe.db.sql("delete from `tabEmail Queue`")

def create_user_if_not_exists(email, first_name = None):
	frappe.delete_doc_if_exists("User", email)

	frappe.get_doc({
		"doctype": "User",
		"user_type": "Website User",
		"email": email,
		"send_welcome_email": 0,
		"first_name": first_name or email.split("@")[0],
		"birth_date": frappe.utils.now_datetime()
	}).insert(ignore_permissions=True)
