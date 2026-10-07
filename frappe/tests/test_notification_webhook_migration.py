# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.email.doctype.notification.notification import Notification
from frappe.integrations.doctype.notification_webhook_url.notification_webhook_url import (
	NotificationWebhookURL,
)
from frappe.patches.v16_0 import rename_slack_webhook_url
from frappe.patches.v16_0.migrate_slack_notifications import execute, migrate_notification_links
from frappe.tests import IntegrationTestCase


class TestNotificationWebhookMigration(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.db.savepoint("notification_webhook_migration_test")
		self.addCleanup(frappe.db.rollback, save_point="notification_webhook_migration_test")

	def _make_webhook(self, service="Slack", show_document_link=0):
		webhook = NotificationWebhookURL.docs.new()
		webhook.webhook_name = f"Migration webhook {frappe.generate_hash(length=8)}"
		webhook.webhook_url = "https://hooks.example.com/notification"
		webhook.set("service", service)
		webhook.show_document_link = show_document_link
		return webhook.insert()

	def _make_notification(self, target=None):
		notification = Notification.docs.new()
		notification.name = f"Migration notification {frappe.generate_hash(length=8)}"
		notification.document_type = "User"
		notification.channel = "Webhook"
		notification.notification_webhook_url = target
		notification.subject = "Webhook migration"
		notification.event = "Method"
		notification.method = "after_insert"
		notification.enabled = 0
		return notification.insert()

	def test_copy_legacy_links_preserves_existing_target(self):
		legacy_target = self._make_webhook()
		new_target = self._make_webhook("Discord")
		missing_link = self._make_notification(legacy_target.name)
		existing_link = self._make_notification(new_target.name)
		for notification in (missing_link, existing_link):
			frappe.db.set_value(
				"Notification", notification.name, {"channel": "Slack", "property_value": legacy_target.name}
			)
		frappe.db.set_value("Notification", missing_link.name, "notification_webhook_url", None)

		# Fresh installations have no legacy column. Reuse a text column to exercise the
		# data-copy query without DDL, which would commit unrelated test transactions.
		doc_type = frappe.qb.DocType
		table = doc_type("Notification")
		table.slack_webhook_url = table.property_value
		with patch.object(
			frappe.qb, "DocType", side_effect=lambda dt: table if dt == "Notification" else doc_type(dt)
		):
			migrate_notification_links()
			migrate_notification_links()

		self.assertEqual(missing_link.reload().notification_webhook_url, legacy_target.name)
		self.assertEqual(existing_link.reload().notification_webhook_url, new_target.name)

	def test_rerun_preserves_service_and_document_link_settings(self):
		slack = self._make_webhook(show_document_link=0)
		discord = self._make_webhook("Discord", show_document_link=1)
		notification = self._make_notification(slack.name)
		frappe.db.set_value("Notification Webhook URL", slack.name, "service", None)
		frappe.db.set_value("Notification", notification.name, "channel", "Slack")

		execute()
		execute()

		self.assertEqual(slack.reload().service, "Slack")
		self.assertEqual(slack.show_document_link, 0)
		self.assertEqual(discord.reload().service, "Discord")
		self.assertEqual(discord.show_document_link, 1)
		self.assertEqual(notification.reload().channel, "Webhook")
		self.assertEqual(notification.notification_webhook_url, slack.name)

	def test_rename_happens_before_schema_sync(self):
		from frappe.modules.patch_handler import PatchType, get_patches_from_app

		self.assertIn(
			"frappe.patches.v16_0.rename_slack_webhook_url",
			get_patches_from_app("frappe", PatchType.pre_model_sync),
		)
		self.assertIn(
			"frappe.patches.v16_0.migrate_slack_notifications",
			get_patches_from_app("frappe", PatchType.post_model_sync),
		)
		with (
			patch.object(frappe.db, "exists", return_value=True),
			patch.object(frappe, "rename_doc") as rename,
		):
			rename_slack_webhook_url.execute()
			rename.assert_called_once_with("DocType", "Slack Webhook URL", "Notification Webhook URL")

	def test_fresh_install_does_not_rename(self):
		with (
			patch.object(frappe.db, "exists", return_value=False),
			patch.object(frappe, "rename_doc") as rename,
		):
			rename_slack_webhook_url.execute()
			rename.assert_not_called()
