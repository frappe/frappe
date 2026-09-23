# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.email.inbox import create_email_flag_queue, get_outgoing_senders
from frappe.tests import IntegrationTestCase


class TestInbox(IntegrationTestCase):
	def test_create_email_flag_queue_accepts_native_list(self):
		comm = frappe.get_doc(
			doctype="Communication",
			communication_type="Communication",
			content="test inbox flag",
			subject="test inbox flag",
			sent_or_received="Received",
		).insert(ignore_permissions=True)

		# names as a native list instead of a JSON string (frappe.parse_json passthrough);
		# the communication has no uid so it is skipped, but the parse_json loop is exercised
		create_email_flag_queue([comm.name], "Read")
		comm.delete()


class TestOutgoingSenders(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.db.savepoint("outgoing_senders")
		self.addCleanup(lambda: frappe.db.rollback(save_point="outgoing_senders"))
		frappe.db.delete("User Email", {"parent": frappe.session.user})
		frappe.db.set_value("Email Account", {"default_outgoing": 1}, "default_outgoing", 0)
		self.enterContext(patch.dict(frappe.conf, {"mail_server": None}))

	def test_no_rows_and_no_default(self):
		self.assertEqual(get_outgoing_senders(), {"senders": [], "default": None})

	def test_one_outgoing_row(self):
		self.add_user_email("me@example.com", enable_outgoing=1)
		self.assertEqual(get_outgoing_senders()["senders"], ["me@example.com"])

	def test_incoming_only_row_is_ignored(self):
		self.add_user_email("inbox@example.com", enable_outgoing=0)
		self.add_user_email("me@example.com", enable_outgoing=1)
		self.assertEqual(get_outgoing_senders()["senders"], ["me@example.com"])

	def test_senders_keep_row_order_without_repeats(self):
		self.add_user_email("second@example.com", enable_outgoing=1, idx=2)
		self.add_user_email("first@example.com", enable_outgoing=1, idx=1)
		self.add_user_email("second@example.com", enable_outgoing=1, idx=3)
		self.assertEqual(get_outgoing_senders()["senders"], ["first@example.com", "second@example.com"])

	def test_default_outgoing_account_is_reported(self):
		frappe.get_doc(
			doctype="Email Account",
			name="_Test Default Outgoing",
			email_account_name="_Test Default Outgoing",
			email_id="notify@example.com",
			enable_outgoing=1,
			default_outgoing=1,
		).db_insert()
		self.assertEqual(get_outgoing_senders(), {"senders": [], "default": "notify@example.com"})

	def add_user_email(self, email_id, enable_outgoing, idx=1):
		frappe.get_doc(
			doctype="User Email",
			parent=frappe.session.user,
			parenttype="User",
			parentfield="user_emails",
			idx=idx,
			email_id=email_id,
			enable_outgoing=enable_outgoing,
		).db_insert()
