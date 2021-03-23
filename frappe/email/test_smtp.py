# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: The MIT License

import unittest
import frappe
from frappe.email.smtp import SMTPServer
from frappe.email.smtp import get_outgoing_email_account

class TestSMTP(unittest.TestCase):
	def test_smtp_ssl_session(self):
		for port in [None, 0, 465, "465"]:
			make_server(port, 1, 0)

	def test_smtp_tls_session(self):
		for port in [None, 0, 587, "587"]:
			make_server(port, 0, 1)

	def test_get_email_account(self):
		frappe.set_user("Administrator")
		frappe.db.sql("delete from `tabEmail Account`")

		# remove mail_server config so that test@example.com is not created
		mail_server = frappe.conf.get('mail_server')
		del frappe.conf['mail_server']

		# lowest preference given to email account with only incoming enabled
		create_email_account(email_id="outgoing_enabled@gmail.com", password="***", enable_outgoing = 1)
		self.assertEqual(get_outgoing_email_account().email_id, "outgoing_enabled@gmail.com")
		frappe.local.outgoing_email_account = {}

		# second highest preference given to email account with default incoming enabled
		create_email_account(email_id="default_outgoing_enabled@gmail.com", password="***", enable_outgoing = 1, default_outgoing=1)
		self.assertEqual(get_outgoing_email_account().email_id, "default_outgoing_enabled@gmail.com")
		frappe.local.outgoing_email_account = {}

		# highest preference given to email account with append_to matching
		create_email_account(email_id="append_to@gmail.com", password="***", enable_outgoing = 1, default_outgoing=1, append_to="Issue")
		self.assertEqual(get_outgoing_email_account(append_to="Issue").email_id, "append_to@gmail.com")

		# add back the mail_server
		frappe.conf['mail_server'] = mail_server

def create_email_account(email_id, password, enable_outgoing, default_outgoing=0, append_to=None):
	email_dict = {
		"email_id": email_id,
		"passsword": password,
		"enable_outgoing":enable_outgoing ,
		"default_outgoing":default_outgoing ,
		"enable_incoming": 1,
		"append_to":append_to,
		"is_dummy_password": 1,
		"smtp_server": "localhost"
	}

	email_account = frappe.new_doc('Email Account')
	email_account.update(email_dict)
	email_account.save()

def make_server(port, ssl, tls):
	server = SMTPServer(
		server = "smtp.gmail.com",
		port = port,
		use_ssl = ssl,
		use_tls = tls
	)

	server.sess