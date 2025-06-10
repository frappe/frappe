# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: The MIT License

import frappe
from frappe.email.doctype.email_account.email_account import EmailAccount
from frappe.email.smtp import SMTPServer
from frappe.tests import IntegrationTestCase


class TestSMTP(IntegrationTestCase):
	def test_smtp_ssl_session(self):
		for port in [None, 0, 465, "465"]:
			make_server(port, 1, 0)

	def test_smtp_tls_session(self):
		for port in [None, 0, 587, "587"]:
			make_server(port, 0, 1)

	def test_get_email_account(self):
		existing_email_accounts = frappe.get_all(
			"Email Account", fields=["name", "enable_outgoing", "default_outgoing", "append_to", "use_imap"]
		)
		unset_details = {"enable_outgoing": 0, "default_outgoing": 0, "append_to": None, "use_imap": 0}
		for email_account in existing_email_accounts:
			frappe.db.set_value("Email Account", email_account["name"], unset_details)

		# remove mail_server config so that test@example.com is not created
		mail_server = frappe.conf.get("mail_server")
		del frappe.conf["mail_server"]

		frappe.local.outgoing_email_account = {}

		frappe.local.outgoing_email_account = {}
		# lowest preference given to email account with default incoming enabled
		create_email_account(
			email_id="default_outgoing_enabled@gmail.com",
			password="password",
			enable_outgoing=1,
			default_outgoing=1,
		)
		self.assertEqual(EmailAccount.find_outgoing().email_id, "default_outgoing_enabled@gmail.com")

		frappe.local.outgoing_email_account = {}
		# highest preference given to email account with append_to matching
		create_email_account(
			email_id="append_to@gmail.com",
			password="password",
			enable_outgoing=1,
			default_outgoing=1,
			append_to="Todo",
		)
		self.assertEqual(EmailAccount.find_outgoing(match_by_doctype="Todo").email_id, "append_to@gmail.com")

		# add back the mail_server
		frappe.conf["mail_server"] = mail_server
		for email_account in existing_email_accounts:
			set_details = {
				"enable_outgoing": email_account["enable_outgoing"],
				"default_outgoing": email_account["default_outgoing"],
				"append_to": email_account["append_to"],
			}
			frappe.db.set_value("Email Account", email_account["name"], set_details)


def create_email_account(email_id, password, enable_outgoing, default_outgoing=0, append_to=None):
	email_dict = {
		"email_id": email_id,
		"passsword": password,
		"enable_outgoing": enable_outgoing,
		"default_outgoing": default_outgoing,
		"enable_incoming": 1,
		"append_to": append_to,
		"is_dummy_password": 1,
		"smtp_server": "127.0.0.1",
		"use_imap": 0,
	}

	email_account = frappe.new_doc("Email Account")
	email_account.update(email_dict)
	email_account.save()


def make_server(port, ssl, tls):
	server = SMTPServer(server="smtp.gmail.com", port=port, use_ssl=ssl, use_tls=tls)

	server.session
