# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import unittest, frappe

from frappe.test_runner import make_test_records
make_test_records("User")
make_test_records("Email Account")

class TestEmail(unittest.TestCase):
	def setUp(self):
		frappe.db.sql("""delete from `tabEmail Unsubscribe`""")
		frappe.db.sql("""delete from `tabBulk Email`""")

	def test_send(self):
		from frappe.email import sendmail
		sendmail('test@example.com', subject='Test Mail', msg="Test Content")

	def test_bulk(self, send_after=None):
		from frappe.email.bulk import send
		send(recipients = ['test@example.com', 'test1@example.com'],
			sender="admin@example.com",
			reference_doctype='User', reference_name='Administrator',
			subject='Testing Bulk', message='This is a bulk mail!', send_after=send_after)

		bulk = frappe.db.sql("""select * from `tabBulk Email` where status='Not Sent'""", as_dict=1)
		self.assertEquals(len(bulk), 2)
		self.assertTrue('test@example.com' in [d['recipient'] for d in bulk])
		self.assertTrue('test1@example.com' in [d['recipient'] for d in bulk])
		self.assertTrue('Unsubscribe' in bulk[0]['message'])

	def test_flush(self):
		self.test_bulk(send_after = 1)
		from frappe.email.bulk import flush
		flush(from_test=True)
		bulk = frappe.db.sql("""select * from `tabBulk Email` where status='Sent'""", as_dict=1)
		self.assertEquals(len(bulk), 0)

	def test_send_after(self):
		self.test_bulk()
		from frappe.email.bulk import flush
		flush(from_test=True)
		bulk = frappe.db.sql("""select * from `tabBulk Email` where status='Sent'""", as_dict=1)
		self.assertEquals(len(bulk), 2)
		self.assertTrue('test@example.com' in [d['recipient'] for d in bulk])
		self.assertTrue('test1@example.com' in [d['recipient'] for d in bulk])

	def test_expired(self):
		self.test_bulk()
		frappe.db.sql("update `tabBulk Email` set creation='2010-01-01 12:00:00'")
		from frappe.email.bulk import flush
		flush(from_test=True)
		bulk = frappe.db.sql("""select * from `tabBulk Email` where status='Expired'""", as_dict=1)
		self.assertEquals(len(bulk), 2)
		self.assertTrue('test@example.com' in [d['recipient'] for d in bulk])
		self.assertTrue('test1@example.com' in [d['recipient'] for d in bulk])

	def test_unsubscribe(self):
		from frappe.email.bulk import unsubscribe, send
		unsubscribe(doctype="User", name="Administrator", email="test@example.com")

		self.assertTrue(frappe.db.get_value("Email Unsubscribe",
			{"reference_doctype": "User", "reference_name": "Administrator", "email": "test@example.com"}))

		send(recipients = ['test@example.com', 'test1@example.com'],
			sender="admin@example.com",
			reference_doctype='User', reference_name= "Administrator",
			subject='Testing Bulk', message='This is a bulk mail!')

		bulk = frappe.db.sql("""select * from `tabBulk Email` where status='Not Sent'""",
			as_dict=1)
		self.assertEquals(len(bulk), 1)
		self.assertFalse('test@example.com' in [d['recipient'] for d in bulk])
		self.assertTrue('test1@example.com' in [d['recipient'] for d in bulk])
		self.assertTrue('Unsubscribe' in bulk[0]['message'])

	def test_bulk_limit(self):
		from frappe.email.bulk import send, BulkLimitCrossedError
		self.assertRaises(BulkLimitCrossedError, send,
			recipients=['test@example.com']*1000,
			sender="admin@example.com",
			reference_doctype = "User", reference_name="Administrator",
			subject='Testing Bulk', message='This is a bulk mail!')


if __name__=='__main__':
	frappe.connect()
	unittest.main()
