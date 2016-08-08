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
		frappe.db.sql("""delete from `tabEmail Queue`""")

	def test_send(self):
		from frappe.email import sendmail
		sendmail('test@example.com', subject='Test Mail', msg="Test Content")

	def test_email_queue(self, send_after=None):
		from frappe.email.queue import send
		send(recipients = ['test@example.com', 'test1@example.com'],
			sender="admin@example.com",
			reference_doctype='User', reference_name='Administrator',
			subject='Testing Queue', message='This mail is queued!', send_after=send_after)

		email_queue = frappe.db.sql("""select * from `tabEmail Queue` where status='Not Sent'""", as_dict=1)
		self.assertEquals(len(email_queue), 2)
		self.assertTrue('test@example.com' in [d['recipient'] for d in email_queue])
		self.assertTrue('test1@example.com' in [d['recipient'] for d in email_queue])
		self.assertTrue('Unsubscribe' in email_queue[0]['message'])

	def test_flush(self):
		self.test_email_queue(send_after = 1)
		from frappe.email.queue import flush
		flush(from_test=True)
		email_queue = frappe.db.sql("""select * from `tabEmail Queue` where status='Sent'""", as_dict=1)
		self.assertEquals(len(email_queue), 0)

	def test_send_after(self):
		self.test_email_queue()
		from frappe.email.queue import flush
		flush(from_test=True)
		email_queue = frappe.db.sql("""select * from `tabEmail Queue` where status='Sent'""", as_dict=1)
		self.assertEquals(len(email_queue), 2)
		self.assertTrue('test@example.com' in [d['recipient'] for d in email_queue])
		self.assertTrue('test1@example.com' in [d['recipient'] for d in email_queue])

	def test_expired(self):
		self.test_email_queue()
		frappe.db.sql("update `tabEmail Queue` set creation=DATE_SUB(curdate(), interval 8 day)")
		from frappe.email.queue import clear_outbox
		clear_outbox()
		email_queue = frappe.db.sql("""select * from `tabEmail Queue` where status='Expired'""", as_dict=1)
		self.assertEquals(len(email_queue), 2)
		self.assertTrue('test@example.com' in [d['recipient'] for d in email_queue])
		self.assertTrue('test1@example.com' in [d['recipient'] for d in email_queue])

	def test_unsubscribe(self):
		from frappe.email.queue import unsubscribe, send
		unsubscribe(doctype="User", name="Administrator", email="test@example.com")

		self.assertTrue(frappe.db.get_value("Email Unsubscribe",
			{"reference_doctype": "User", "reference_name": "Administrator", "email": "test@example.com"}))

		before = frappe.db.sql("""select count(name) from `tabEmail Queue` where status='Not Sent'""")[0][0]

		send(recipients = ['test@example.com', 'test1@example.com'],
			sender="admin@example.com",
			reference_doctype='User', reference_name= "Administrator",
			subject='Testing Email Queue', message='This is mail is queued!')

		# this is sent async (?)

		email_queue = frappe.db.sql("""select * from `tabEmail Queue` where status='Not Sent'""",
			as_dict=1)
		self.assertEquals(len(email_queue), before + 1)
		self.assertFalse('test@example.com' in [d['recipient'] for d in email_queue])
		self.assertTrue('test1@example.com' in [d['recipient'] for d in email_queue])
		self.assertTrue('Unsubscribe' in email_queue[0]['message'])

	def test_email_queue_limit(self):
		from frappe.email.queue import send, EmailLimitCrossedError
		self.assertRaises(EmailLimitCrossedError, send,
			recipients=['test@example.com']*1000,
			sender="admin@example.com",
			reference_doctype = "User", reference_name="Administrator",
			subject='Testing Email Queue', message='This email is queued!')

	def test_image_parsing(self):
		import re
		email_account = frappe.get_doc('Email Account', '_Test Email Account 1')

		with open(frappe.get_app_path('frappe', 'tests', 'data', 'email_with_image.txt'), 'r') as raw:
			communication = email_account.insert_communication(raw.read())

		#print communication.content
		self.assertTrue(re.search('''<img[^>]*src=["']/private/files/rtco1.png[^>]*>''', communication.content))
		self.assertTrue(re.search('''<img[^>]*src=["']/private/files/rtco2.png[^>]*>''', communication.content))


if __name__=='__main__':
	frappe.connect()
	unittest.main()
