# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe, unittest

class TestDynamicLinks(unittest.TestCase):
	def setUp(self):
		frappe.db.sql('delete from `tabEmail Unsubscribe`')

	def test_delete_normal(self):
		event = frappe.get_doc({
			'doctype': 'Event',
			'subject':'test-for-delete',
			'starts_on': '2014-01-01',
			'event_type': 'Public'
		}).insert()

		unsub = frappe.get_doc({
			'doctype': 'Email Unsubscribe',
			'email': 'test@example.com',
			'reference_doctype': event.doctype,
			'reference_name': event.name
		}).insert()

		event.delete()

		self.assertFalse(frappe.db.exists('Email Unsubscribe', unsub.name))

	def test_delete_with_comment(self):
		event = frappe.get_doc({
			'doctype': 'Event',
			'subject':'test-for-delete-1',
			'starts_on': '2014-01-01',
			'event_type': 'Public'
		}).insert()
		event.add_comment('Comment', 'test')

		self.assertTrue(frappe.get_all('Comment',
			filters={'reference_doctype':'Event', 'reference_name':event.name}))
		event.delete()
		self.assertFalse(frappe.get_all('Comment',
			filters={'reference_doctype':'Event', 'reference_name':event.name}))

	def test_custom_fields(self):
		from frappe.utils.testutils import add_custom_field, clear_custom_fields
		add_custom_field('Event', 'test_ref_doc', 'Link', 'DocType')
		add_custom_field('Event', 'test_ref_name', 'Dynamic Link', 'test_ref_doc')

		unsub = frappe.get_doc({
			'doctype': 'Email Unsubscribe',
			'email': 'test@example.com',
			'global_unsubscribe': 1
		}).insert()

		event = frappe.get_doc({
			'doctype': 'Event',
			'subject':'test-for-delete-2',
			'starts_on': '2014-01-01',
			'event_type': 'Public',
			'test_ref_doc': unsub.doctype,
			'test_ref_name': unsub.name
		}).insert()

		self.assertRaises(frappe.LinkExistsError, unsub.delete)

		event.test_ref_doc = None
		event.test_ref_name = None
		event.save()

		unsub.delete()

		clear_custom_fields('Event')
