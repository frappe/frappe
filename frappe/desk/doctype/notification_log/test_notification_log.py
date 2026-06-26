# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.core.doctype.user.user import get_system_users
from frappe.desk.doctype.notification_log.notification_log import (
	UNREAD_COUNT_CACHE_KEY,
	NotificationLog,
	enqueue_create_notification,
	get_email_header,
	get_unread_count,
	mark_all_as_read,
	mark_as_read,
)
from frappe.desk.doctype.notification_settings.notification_settings import create_notification_settings
from frappe.desk.doctype.notification_type.notification_type import install_notification_types
from frappe.desk.form.assign_to import add as assign_task
from frappe.tests import IntegrationTestCase


class TestNotificationLog(IntegrationTestCase):
	def test_assignment(self):
		todo = get_todo()
		user = get_user()

		assign_task(
			{"assign_to": [user], "doctype": "ToDo", "name": todo.name, "description": todo.description}
		)
		log_type = frappe.db.get_value(
			"Notification Log", {"document_type": "ToDo", "document_name": todo.name}, "type"
		)
		self.assertEqual(log_type, "Assignment")

	def test_share(self):
		todo = get_todo()
		user = get_user()

		frappe.share.add("ToDo", todo.name, user, notify=1)
		log_type = frappe.db.get_value(
			"Notification Log", {"document_type": "ToDo", "document_name": todo.name}, "type"
		)
		self.assertEqual(log_type, "Share")

		email = get_last_email_queue()
		content = f"Subject: {frappe.utils.get_fullname(frappe.session.user)} shared a document ToDo"
		self.assertTrue(content in email.message)

	def test_type_link_conversion_alert_still_self_notifies(self):
		"""`type` is now a Link, but an `Alert` must still insert even for the sender."""
		install_notification_types()
		user = get_user()
		enqueue_create_notification(
			[user],
			{"type": "Alert", "subject": "Self alert", "from_user": user, "link": "/app"},
		)
		self.assertTrue(frappe.db.exists("Notification Log", {"for_user": user, "subject": "Self alert"}))

	def test_get_email_header_unknown_type_falls_back(self):
		"""A custom type with no header_map entry must not KeyError."""
		doc = frappe._dict(type="Some Custom Type", document_name="X", email_header=None)
		self.assertEqual(get_email_header(doc), get_email_header(frappe._dict(type="", document_name="X")))

	def test_enqueue_create_notification_fans_out(self):
		install_notification_types()
		recipient = make_recipient("notify_fanout@example.com")
		enqueue_create_notification(
			[recipient],
			{"type": "Mention", "subject": "Hello there", "from_user": "Administrator", "link": "/app"},
		)
		self.assertTrue(
			frappe.db.exists(
				"Notification Log", {"for_user": recipient, "subject": "Hello there", "type": "Mention"}
			)
		)

	def test_dedupe_on_prevents_duplicate_rows(self):
		install_notification_types()
		recipient = make_recipient("notify_dedupe@example.com")
		for _ in range(2):
			enqueue_create_notification(
				[recipient],
				{
					"type": "Mention",
					"subject": "Dup subject",
					"document_type": "ToDo",
					"document_name": "DEDUP-1",
					"from_user": "Administrator",
				},
				dedupe_on=["type", "document_name"],
			)
		count = frappe.db.count(
			"Notification Log", {"for_user": recipient, "document_name": "DEDUP-1", "type": "Mention"}
		)
		self.assertEqual(count, 1)

	def test_custom_field_passthrough(self):
		"""Unknown extra fields are ignored; a matching Custom Field receives the value."""
		from frappe.custom.doctype.custom_field.custom_field import create_custom_field

		install_notification_types()
		create_custom_field(
			"Notification Log",
			{"fieldname": "assistance_url", "label": "Assistance URL", "fieldtype": "Data"},
		)

		def _remove_custom_field():
			frappe.delete_doc(
				"Custom Field", "Notification Log-assistance_url", ignore_missing=True, force=True
			)
			frappe.clear_cache(doctype="Notification Log")

		# remove the throwaway field once the test finishes (even if an assertion fails)
		self.addCleanup(_remove_custom_field)
		frappe.clear_cache(doctype="Notification Log")
		recipient = make_recipient("notify_customfield@example.com")
		enqueue_create_notification(
			[recipient],
			{
				"type": "Mention",
				"subject": "With custom field",
				"from_user": "Administrator",
				"link": "/app",
				"assistance_url": "https://docs.example.com/fix",
				"ignored_field": "this is silently dropped",
			},
		)
		name = frappe.db.get_value(
			"Notification Log", {"for_user": recipient, "subject": "With custom field"}
		)
		self.assertEqual(
			frappe.db.get_value("Notification Log", name, "assistance_url"),
			"https://docs.example.com/fix",
		)

	def test_app_derived_from_document_type(self):
		"""`app` is filled from the reference document's owning app on insert."""
		install_notification_types()
		recipient = make_recipient("notify_app_derive@example.com")
		enqueue_create_notification(
			[recipient],
			{
				"type": "Mention",
				"subject": "Derived app",
				"document_type": "ToDo",  # owned by frappe
				"document_name": "APP-DERIVE-1",
				"from_user": "Administrator",
			},
		)
		app = frappe.db.get_value(
			"Notification Log", {"for_user": recipient, "subject": "Derived app"}, "app"
		)
		self.assertEqual(app, "frappe")

	def test_app_explicit_not_overwritten(self):
		"""An explicitly supplied `app` is preserved, not re-derived from document_type."""
		install_notification_types()
		recipient = make_recipient("notify_app_explicit@example.com")
		enqueue_create_notification(
			[recipient],
			{
				"type": "Mention",
				"subject": "Explicit app",
				"app": "crm",
				"document_type": "ToDo",  # would derive to frappe, but explicit wins
				"document_name": "APP-EXPLICIT-1",
				"from_user": "Administrator",
			},
		)
		app = frappe.db.get_value(
			"Notification Log", {"for_user": recipient, "subject": "Explicit app"}, "app"
		)
		self.assertEqual(app, "crm")

	def test_app_empty_when_no_document_type(self):
		"""No document_type and no explicit app => global-only (`app` left empty)."""
		install_notification_types()
		recipient = make_recipient("notify_app_none@example.com")
		enqueue_create_notification(
			[recipient],
			{
				"type": "Mention",
				"subject": "No app",
				"from_user": "Administrator",
				"link": "/app",
			},
		)
		app = frappe.db.get_value("Notification Log", {"for_user": recipient, "subject": "No app"}, "app")
		self.assertFalse(app)


def make_recipient(email: str) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
	return email


class TestNotificationUnreadCount(IntegrationTestCase):
	def setUp(self):
		self.user = "test@example.com"
		create_notification_settings(self.user)
		frappe.db.delete("Notification Log", {"for_user": self.user})
		frappe.cache.delete_value(UNREAD_COUNT_CACHE_KEY, user=self.user)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.delete("Notification Log", {"for_user": self.user})
		frappe.cache.delete_value(UNREAD_COUNT_CACHE_KEY, user=self.user)

	def _insert_log(self, for_user=None):
		return frappe.get_doc(
			{
				"doctype": "Notification Log",
				"subject": "test",
				"for_user": for_user or self.user,
				"from_user": "Administrator",
				"type": "Alert",
			}
		).insert(ignore_permissions=True)

	def _flush_after_commit(self):
		frappe.db.after_commit.run()

	def test_cold_cache_computes_from_log(self):
		self._insert_log()
		self._insert_log()
		frappe.cache.delete_value(UNREAD_COUNT_CACHE_KEY, user=self.user)

		self.assertEqual(get_unread_count(self.user), 2)
		self.assertEqual(frappe.cache.get_value(UNREAD_COUNT_CACHE_KEY, user=self.user, expires=True), 2)

	def test_returns_cached_value(self):
		frappe.cache.set_value(UNREAD_COUNT_CACHE_KEY, 7, user=self.user, expires_in_sec=60)
		self.assertEqual(get_unread_count(self.user), 7)

	def test_insert_invalidates_cache(self):
		frappe.cache.set_value(UNREAD_COUNT_CACHE_KEY, 0, user=self.user, expires_in_sec=60)
		self._insert_log()
		self._flush_after_commit()

		self.assertIsNone(frappe.cache.get_value(UNREAD_COUNT_CACHE_KEY, user=self.user, expires=True))
		self.assertEqual(get_unread_count(self.user), 1)

	def test_mark_as_read_invalidates_cache(self):
		log = self._insert_log()
		self._insert_log()
		self._flush_after_commit()
		get_unread_count(self.user)

		frappe.set_user(self.user)
		mark_as_read(log.name)
		self._flush_after_commit()

		self.assertEqual(frappe.db.get_value("Notification Log", log.name, "read"), 1)
		self.assertIsNone(frappe.cache.get_value(UNREAD_COUNT_CACHE_KEY, user=self.user, expires=True))
		self.assertEqual(get_unread_count(self.user), 1)

	def test_mark_all_as_read_invalidates_cache(self):
		for _ in range(3):
			self._insert_log()
		self._flush_after_commit()
		get_unread_count(self.user)

		frappe.set_user(self.user)
		mark_all_as_read()
		self._flush_after_commit()

		self.assertIsNone(frappe.cache.get_value(UNREAD_COUNT_CACHE_KEY, user=self.user, expires=True))
		self.assertEqual(get_unread_count(self.user), 0)

	def test_clear_old_logs_invalidates_cache(self):
		from frappe.utils import add_to_date, now_datetime

		log = self._insert_log()
		frappe.db.set_value(
			"Notification Log",
			log.name,
			"creation",
			add_to_date(now_datetime(), days=-200),
			update_modified=False,
		)
		frappe.cache.set_value(UNREAD_COUNT_CACHE_KEY, 5, user=self.user, expires_in_sec=60)

		NotificationLog.clear_old_logs(days=180)
		self._flush_after_commit()

		self.assertIsNone(frappe.cache.get_value(UNREAD_COUNT_CACHE_KEY, user=self.user, expires=True))
		self.assertFalse(frappe.db.exists("Notification Log", log.name))

	def test_mark_as_read_does_not_affect_other_user(self):
		other_user = "test1@example.com"
		create_notification_settings(other_user)
		frappe.db.delete("Notification Log", {"for_user": other_user})
		frappe.cache.delete_value(UNREAD_COUNT_CACHE_KEY, user=other_user)
		log = self._insert_log(for_user=other_user)
		self._flush_after_commit()

		frappe.set_user(self.user)
		mark_as_read(log.name)
		self._flush_after_commit()

		self.assertEqual(frappe.db.get_value("Notification Log", log.name, "read"), 0)
		self.assertEqual(get_unread_count(other_user), 1)

		frappe.set_user("Administrator")
		frappe.db.delete("Notification Log", {"for_user": other_user})
		frappe.cache.delete_value(UNREAD_COUNT_CACHE_KEY, user=other_user)


def get_last_email_queue():
	res = frappe.get_all("Email Queue", fields=["message"], order_by="creation desc", limit=1)
	return res[0]


def get_todo():
	if not frappe.get_all("ToDo"):
		return frappe.get_doc({"doctype": "ToDo", "description": "Test for Notification"}).insert()

	res = frappe.get_all("ToDo", limit=1)
	return frappe.get_cached_doc("ToDo", res[0].name)


def get_user():
	return get_system_users(limit=1)[0]
