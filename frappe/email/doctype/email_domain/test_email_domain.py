# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import ssl
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.tests.utils import make_test_objects


class TestDomain(IntegrationTestCase):
	def setUp(self):
		make_test_objects("Email Domain", reset=True)

	def tearDown(self):
		frappe.delete_doc("Email Account", "Test")
		frappe.delete_doc("Email Domain", "test.com")

	def test_on_update(self):
		mail_domain = frappe.get_doc("Email Domain", "test.com")
		mail_account = frappe.get_doc("Email Account", "Test")

		# Ensure a different port
		mail_account.incoming_port = int(mail_domain.incoming_port) + 5
		mail_account.save()
		# Trigger update of accounts using this domain
		mail_domain.on_update()

		mail_account.reload()
		# After update, incoming_port in account should match the domain
		self.assertEqual(mail_account.incoming_port, mail_domain.incoming_port)

		# Also make sure that the other attributes match
		self.assertEqual(mail_account.use_imap, mail_domain.use_imap)
		self.assertEqual(mail_account.use_ssl, mail_domain.use_ssl)
		self.assertEqual(mail_account.use_starttls, mail_domain.use_starttls)
		self.assertEqual(mail_account.use_tls, mail_domain.use_tls)
		self.assertEqual(mail_account.attachment_limit, mail_domain.attachment_limit)
		self.assertEqual(mail_account.smtp_server, mail_domain.smtp_server)
		self.assertEqual(mail_account.smtp_port, mail_domain.smtp_port)

	def test_outgoing_certificate_setting_reaches_email_account(self):
		mail_domain = frappe.get_doc("Email Domain", "test.com")
		mail_account = frappe.get_doc("Email Account", "Test")

		for validate in (0, 1):
			mail_domain.db_set("validate_ssl_certificate_for_outgoing", validate)
			self.assertEqual(mail_account.sendmail_config()["validate_ssl_certificate"], bool(validate))

		mail_account.domain = None
		self.assertTrue(mail_account.sendmail_config()["validate_ssl_certificate"])

	def test_outgoing_connection_validates_certificate_for_ssl_and_starttls(self):
		mail_domain = frappe.get_doc("Email Domain", "test.com")
		mail_domain.smtp_server = "smtp.example.com"

		for use_ssl in (0, 1):
			for validate in (0, 1):
				with self.subTest(use_ssl=use_ssl, validate=validate):
					mail_domain.use_ssl_for_outgoing = use_ssl
					mail_domain.use_tls = 1 - use_ssl
					mail_domain.smtp_port = None
					mail_domain.validate_ssl_certificate_for_outgoing = validate
					with (
						patch("frappe.email.doctype.email_domain.email_domain.smtplib.SMTP") as smtp,
						patch("frappe.email.doctype.email_domain.email_domain.smtplib.SMTP_SSL") as smtp_ssl,
					):
						mail_domain.validate_outgoing_server_conn()

					if use_ssl:
						context = smtp_ssl.call_args.kwargs["context"]
						smtp.assert_not_called()
					else:
						context = smtp.return_value.starttls.call_args.kwargs["context"]
						smtp_ssl.assert_not_called()

					self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED if validate else ssl.CERT_NONE)
					self.assertEqual(context.check_hostname, bool(validate))

	def test_outgoing_plain_connection_does_not_start_tls(self):
		mail_domain = frappe.get_doc("Email Domain", "test.com")
		mail_domain.smtp_server = "smtp.example.com"
		mail_domain.use_ssl_for_outgoing = 0
		mail_domain.use_tls = 0

		with patch("frappe.email.doctype.email_domain.email_domain.smtplib.SMTP") as smtp:
			mail_domain.validate_outgoing_server_conn()

		smtp.return_value.starttls.assert_not_called()
