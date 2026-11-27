# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import frappe
from frappe.email.doctype.email_blocklist import email_blocklist
from frappe.email.doctype.email_blocklist.email_blocklist import get_blocked_emails
from frappe.email.doctype.email_queue.email_queue import QueueBuilder
from frappe.tests import IntegrationTestCase


def add_to_blocklist(email_or_domain: str):
	frappe.get_doc({"doctype": "Email Blocklist", "email_or_domain": email_or_domain}).insert()


class TestEmailBlocklist(IntegrationTestCase):
	def setUp(self):
		frappe.db.delete("Email Blocklist")

	def test_blocked_email_is_dropped_from_queue(self):
		add_to_blocklist("Spammer@Example.com")
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")

		builder = QueueBuilder(
			recipients=["Spammer <spammer@example.com>", "test1@example.com"],
			cc=["spammer@example.com"],
			sender="admin@example.com",
			subject="Testing Email Blocklist",
			message="This mail is queued!",
		)

		self.assertEqual(builder.final_recipients(), ["test1@example.com"])
		self.assertEqual(builder.final_cc(), [])

	def test_blocked_domain_covers_subdomains(self):
		add_to_blocklist("spam.example.com")

		self.assertEqual(
			get_blocked_emails(["a@spam.example.com", "b@mail.spam.example.com", "c@example.com"]),
			["a@spam.example.com", "b@mail.spam.example.com"],
		)
		self.assertEqual(get_blocked_emails([]), [])

	def test_shipped_domain_is_blocked_unless_site_allows_it(self):
		emails = ["a@spam.example.com", "b@mail.spam.example.com", "c@example.com"]
		with patch.object(
			email_blocklist, "get_shipped_blocked_domains", return_value=frozenset({"spam.example.com"})
		):
			self.assertEqual(get_blocked_emails(emails), emails[:2])

			with patch.dict(frappe.conf, allow_blocked_email_domains=["Spam.Example.com"]):
				self.assertEqual(get_blocked_emails(emails), [])

	def test_invalid_entries_are_rejected(self):
		for entry in ("not a domain", "localhost", "user@", "@example.com"):
			with self.assertRaises(frappe.ValidationError):
				add_to_blocklist(entry)
