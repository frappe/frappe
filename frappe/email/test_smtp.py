# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: The MIT License

import ssl
from unittest.mock import Mock, patch

import frappe
from frappe.email.doctype.email_account.email_account import EmailAccount
from frappe.email.smtp import SMTPServer
from frappe.tests import IntegrationTestCase


class TestSMTP(IntegrationTestCase):
	def test_discard_session_closes_and_clears_active_session(self):
		server = SMTPServer(server="smtp.example.com")
		fake_session = Mock()
		server._session = fake_session

		server.discard_session()

		fake_session.close.assert_called_once()
		self.assertIsNone(server._session)

	def test_discard_session_suppresses_close_errors(self):
		server = SMTPServer(server="smtp.example.com")
		fake_session = Mock()
		fake_session.close.side_effect = OSError("already disconnected")
		server._session = fake_session

		server.discard_session()  # must not raise

		self.assertIsNone(server._session)

	def test_discard_session_is_noop_without_active_session(self):
		server = SMTPServer(server="smtp.example.com")
		server._session = None

		server.discard_session()  # must not raise

		self.assertIsNone(server._session)

	def test_smtp_ssl_session(self):
		for port in [None, 0, 465, "465"]:
			make_server(port, 1, 0)

	def test_smtp_tls_session(self):
		for port in [None, 0, 587, "587"]:
			make_server(port, 0, 1)

	def test_starttls_uses_default_ssl_context(self):
		server = SMTPServer(server="smtp.example.com", use_tls=1)
		connection = Mock()

		server.secure_session(connection)

		context = connection.starttls.call_args.kwargs["context"]
		self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
		self.assertTrue(context.check_hostname)
		connection.starttls.assert_called_once_with(context=context)

	def test_starttls_skips_certificate_validation_when_disabled(self):
		server = SMTPServer(server="smtp.example.com", use_tls=1, validate_ssl_certificate=0)
		connection = Mock()

		server.secure_session(connection)

		context = connection.starttls.call_args.kwargs["context"]
		self.assertEqual(context.verify_mode, ssl.CERT_NONE)
		self.assertFalse(context.check_hostname)

	@patch("frappe.email.smtp.smtplib.SMTP_SSL")
	def test_smtp_ssl_uses_default_ssl_context(self, smtp_ssl):
		server = SMTPServer(server="smtp.example.com", port=465, use_ssl=1)

		server.session

		context = smtp_ssl.call_args.kwargs["context"]
		self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
		self.assertTrue(context.check_hostname)

	@patch("frappe.email.smtp.smtplib.SMTP_SSL")
	def test_smtp_ssl_skips_certificate_validation_when_disabled(self, smtp_ssl):
		server = SMTPServer(server="smtp.example.com", port=465, use_ssl=1, validate_ssl_certificate=0)

		server.session

		context = smtp_ssl.call_args.kwargs["context"]
		self.assertEqual(context.verify_mode, ssl.CERT_NONE)
		self.assertFalse(context.check_hostname)

	@patch("frappe.email.smtp.smtplib.SMTP_SSL", side_effect=ssl.SSLCertVerificationError(1, "untrusted"))
	def test_smtp_ssl_certificate_error_is_descriptive(self, smtp_ssl):
		server = SMTPServer(server="smtp.example.com", port=465, use_ssl=1)

		with self.assertRaisesRegex(frappe.ValidationError, "Could not verify the TLS certificate"):
			server.session

	@patch("frappe.email.smtp.smtplib.SMTP")
	def test_starttls_certificate_error_closes_connection(self, smtp):
		server = SMTPServer(server="smtp.example.com", port=587, use_tls=1)
		smtp.return_value.starttls.side_effect = ssl.SSLCertVerificationError(1, "untrusted")

		with self.assertRaisesRegex(frappe.ValidationError, "Could not verify the TLS certificate"):
			server.session

		smtp.return_value.close.assert_called_once()
		self.assertIsNone(server._session)

	def test_get_email_account(self):
		existing_email_accounts = frappe.get_all(
			"Email Account",
			fields=["name", "enable_outgoing", "default_outgoing", "append_to", "use_imap"],
		)
		unset_details = {"enable_outgoing": 0, "default_outgoing": 0, "append_to": None, "use_imap": 0}
		for email_account in existing_email_accounts:
			frappe.db.set_value("Email Account", email_account["name"], unset_details)

		# remove mail_server config so that test@example.com is not created
		mail_server = frappe.conf.get("mail_server")
		if "mail_server" in frappe.conf:
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
			append_to="ToDo",
		)
		self.assertEqual(EmailAccount.find_outgoing(match_by_doctype="ToDo").email_id, "append_to@gmail.com")

		# add back the mail_server
		frappe.conf["mail_server"] = mail_server
		for email_account in existing_email_accounts:
			set_details = {
				"enable_outgoing": email_account["enable_outgoing"],
				"default_outgoing": email_account["default_outgoing"],
				"append_to": email_account["append_to"],
			}
			frappe.db.set_value("Email Account", email_account["name"], set_details)

	def test_cached_default_does_not_shadow_specific_outgoing_account(self):
		create_email_account(
			email_id="notifications@example.com", password="password", enable_outgoing=1, default_outgoing=1
		)
		create_email_account(
			email_id="support@example.com", password="password", enable_outgoing=1, append_to="ToDo"
		)
		frappe.local.outgoing_email_account = {}

		self.assertEqual(EmailAccount.find_outgoing().email_id, "notifications@example.com")
		self.assertEqual(
			EmailAccount.find_outgoing(match_by_email="support@example.com").email_id, "support@example.com"
		)
		self.assertEqual(EmailAccount.find_outgoing(match_by_doctype="ToDo").email_id, "support@example.com")
		self.assertEqual(EmailAccount.find_outgoing("support@example.com").email_id, "support@example.com")


class TestSMTPCertificateSettings(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		identifier = frappe.generate_hash(length=8)
		cls.user = f"smtp-certificate-{identifier}@example.com"
		cls.domain_name = f"smtp-certificate-{identifier}.example.com"
		cls.account_name = f"SMTP Certificate {identifier}"
		frappe.get_doc(
			{"doctype": "User", "email": cls.user, "first_name": "SMTP Certificate", "send_welcome_email": 0}
		).insert().add_roles("System Manager")

		with cls.set_user(cls.user):
			frappe.get_doc(
				{
					"doctype": "Email Domain",
					"domain_name": cls.domain_name,
					"email_server": "imap.example.com",
					"smtp_server": "smtp.example.com",
					"use_tls": 1,
					"validate_ssl_certificate_for_outgoing": 1,
				}
			).insert()
			frappe.get_doc(
				{
					"doctype": "Email Account",
					"email_account_name": cls.account_name,
					"email_id": f"smtp@{cls.domain_name}",
					"domain": cls.domain_name,
					"smtp_server": "smtp.example.com",
					"use_tls": 1,
				}
			).insert()

	def test_outgoing_certificate_setting_reaches_email_account(self):
		with self.set_user(self.user):
			self.assertIsNotNone(
				frappe.get_meta("Email Account").get_field("validate_ssl_certificate_for_outgoing")
			)
			domain = frappe.get_doc("Email Domain", self.domain_name)
			account = frappe.get_doc("Email Account", self.account_name)
			account.validate_ssl_certificate_for_outgoing = 0

			for validate in (0, 1):
				domain.validate_ssl_certificate_for_outgoing = validate
				domain.save()
				self.assertEqual(account.sendmail_config()["validate_ssl_certificate"], bool(validate))

			account.reload()
			account.domain = None
			for validate in (0, 1):
				account.validate_ssl_certificate_for_outgoing = validate
				account.save()
				self.assertEqual(account.sendmail_config()["validate_ssl_certificate"], bool(validate))

	def test_outgoing_connection_validates_certificate_for_ssl_and_starttls(self):
		with self.set_user(self.user):
			domain = frappe.get_doc("Email Domain", self.domain_name)
			for use_ssl in (0, 1):
				for validate in (0, 1):
					with self.subTest(use_ssl=use_ssl, validate=validate):
						domain.use_ssl_for_outgoing = use_ssl
						domain.use_tls = 1 - use_ssl
						domain.smtp_port = None
						domain.validate_ssl_certificate_for_outgoing = validate
						with (
							patch("frappe.email.doctype.email_domain.email_domain.smtplib.SMTP") as smtp,
							patch(
								"frappe.email.doctype.email_domain.email_domain.smtplib.SMTP_SSL"
							) as smtp_ssl,
						):
							domain.validate_outgoing_server_conn()

						if use_ssl:
							context = smtp_ssl.call_args.kwargs["context"]
							smtp.assert_not_called()
						else:
							context = smtp.return_value.starttls.call_args.kwargs["context"]
							smtp_ssl.assert_not_called()

						self.assertEqual(
							context.verify_mode, ssl.CERT_REQUIRED if validate else ssl.CERT_NONE
						)
						self.assertEqual(context.check_hostname, bool(validate))

	def test_outgoing_plain_connection_does_not_start_tls(self):
		with self.set_user(self.user):
			domain = frappe.get_doc("Email Domain", self.domain_name)
			domain.use_ssl_for_outgoing = 0
			domain.use_tls = 0

			with patch("frappe.email.doctype.email_domain.email_domain.smtplib.SMTP") as smtp:
				domain.validate_outgoing_server_conn()

			smtp.return_value.starttls.assert_not_called()


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
