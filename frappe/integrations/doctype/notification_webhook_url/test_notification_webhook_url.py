# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from copy import deepcopy
from unittest.mock import Mock, PropertyMock, patch

import requests

import frappe
from frappe.core.doctype.user.user import User
from frappe.email.doctype.notification.notification import Notification
from frappe.integrations.doctype.notification_webhook_url.notification_webhook_url import (
	SERVICE_CLASSES,
	NotificationWebhookURL,
	WebhookDeliveryError,
)
from frappe.modules.import_file import import_doc
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user

TEST_SITE = "https://frappe.example.com"
REFERENCE_NAME = "webhook@example.com"
DOCUMENT_URL = f"{TEST_SITE}/desk/user/{REFERENCE_NAME}"
APP_LOGO = "/assets/frappe/images/test-logo.png"

EXPECTED_PAYLOADS = {
	"Slack": {
		"text": "Test",
		"attachments": [
			{
				"fallback": f"See the document at {DOCUMENT_URL}",
				"actions": [
					{
						"type": "button",
						"text": "Go to the document",
						"url": DOCUMENT_URL,
						"style": "primary",
					}
				],
			}
		],
	},
	"Rocket.Chat": {
		"text": "Test",
		"attachments": [{"title": "Document link", "title_link": DOCUMENT_URL}],
	},
	"Google Chat": {"text": f"Test\n<{DOCUMENT_URL}|Document link>"},
	"Matrix (Hookshot)": {"text": f"Test\n\n[Document link]({DOCUMENT_URL})"},
	"Mattermost": {"text": f"Test\n<{DOCUMENT_URL}|Document link>"},
	"Discord": {
		"content": "Test",
		"username": "Test App",
		"avatar_url": f"{TEST_SITE}{APP_LOGO}",
		"embeds": [{"title": "Document link", "url": DOCUMENT_URL}],
	},
	"Raven": {
		"content": "Test",
		"username": "Test App",
		"avatar_url": f"{TEST_SITE}{APP_LOGO}",
		"embeds": [{"title": "Document link", "url": DOCUMENT_URL}],
	},
}


class TestNotificationWebhookURL(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.db.savepoint("notification_webhook_test")
		self.addCleanup(frappe.db.rollback, save_point="notification_webhook_test")
		self.enterContext(patch.object(frappe.local, "lang", "en"))
		self.enterContext(patch("frappe.utils.data.get_url", self._get_url))
		self.enterContext(
			patch(
				"frappe.integrations.doctype.notification_webhook_url.notification_webhook_url.get_url",
				self._get_url,
			)
		)
		self.website_settings: dict[str, str | None] = {"app_name": "Test App", "app_logo": APP_LOGO}
		self.enterContext(patch("frappe.get_website_settings", side_effect=self.website_settings.get))
		self.user = User.docs.new()
		self.user.email = f"webhook-{frappe.generate_hash(length=8)}@example.com"
		self.user.first_name = "Webhook Test"
		self.user.send_welcome_email = 0
		self.user.insert()
		assert self.user.name
		self.user_name = self.user.name

	def _get_url(self, uri=""):
		return f"{TEST_SITE}{uri}"

	def _make_webhook(self, service="Slack", show_document_link=1):
		params = NotificationWebhookURL.docs.new()
		params.webhook_name = f"Webhook {frappe.generate_hash(length=8)}"
		params.webhook_url = f"https://hooks.example.com/{frappe.scrub(service)}"
		params.show_document_link = show_document_link
		params.set("service", service)
		return params

	def _make_notification(self, params):
		notification = Notification.docs.new()
		notification.name = f"Webhook notification {frappe.generate_hash(length=8)}"
		notification.document_type = "User"
		notification.channel = "Webhook"
		notification.event = "Method"
		notification.method = "after_insert"
		notification.subject = "User {{ doc.first_name }}"
		notification.message = "Hello {{ doc.first_name }}"
		notification.notification_webhook_url = params.name
		return notification

	def test_service_options(self):
		field = frappe.get_meta("Notification Webhook URL").get_field("service")
		assert field is not None
		self.assertEqual(set(field.options.split("\n")), set(SERVICE_CLASSES))
		self.assertEqual(set(EXPECTED_PAYLOADS) | {"Ntfy", "Teams"}, set(SERVICE_CLASSES))

	def test_send_as_regular_user(self):
		for service, payload in EXPECTED_PAYLOADS.items():
			with (
				self.subTest(service=service),
				set_user(self.user_name),
				patch("requests.post", return_value=Mock(ok=True)) as post,
			):
				params = self._make_webhook(service)
				self.assertEqual(params.send("Test", "User", REFERENCE_NAME), "success")
				post.assert_called_once_with(params.webhook_url, json=payload, timeout=10)

	def test_send_without_document_link(self):
		for service in EXPECTED_PAYLOADS:
			with self.subTest(service=service), patch("requests.post", return_value=Mock(ok=True)) as post:
				params = self._make_webhook(service, show_document_link=0)
				params.send("Test", "User", REFERENCE_NAME)
				expected = (
					{"content": "Test", "username": "Test App", "avatar_url": f"{TEST_SITE}{APP_LOGO}"}
					if service in ("Discord", "Raven")
					else {"text": "Test"}
				)
				post.assert_called_once_with(params.webhook_url, json=expected, timeout=10)

	def test_teams_adaptive_card(self):
		for show_link in (0, 1):
			with (
				self.subTest(show_link=show_link),
				set_user(self.user_name),
				patch("requests.post", return_value=Mock(ok=True)) as post,
			):
				params = self._make_webhook("Teams", show_link)
				self.assertEqual(params.send("Notification reçue", "User", REFERENCE_NAME), "success")
				post.assert_called_once()
				self.assertEqual(post.call_args.args, (params.webhook_url,))
				self.assertEqual(post.call_args.kwargs["timeout"], 10)
				payload = post.call_args.kwargs["json"]
				self.assertEqual(payload["type"], "message")
				self.assertEqual(len(payload["attachments"]), 1)
				attachment = payload["attachments"][0]
				self.assertEqual(attachment["contentType"], "application/vnd.microsoft.card.adaptive")
				card = attachment["content"]
				self.assertEqual(card["type"], "AdaptiveCard")
				self.assertEqual(len(card["body"]), 1)
				self.assertEqual(card["body"][0]["type"], "TextBlock")
				self.assertEqual(card["body"][0]["text"], "Notification reçue")
				self.assertIs(card["body"][0]["wrap"], True)
				actions = card.get("actions", [])
				self.assertEqual(len(actions), show_link)
				if show_link:
					self.assertEqual(actions[0]["type"], "Action.OpenUrl")
					self.assertEqual(actions[0]["title"], "Document link")
					self.assertEqual(actions[0]["url"], DOCUMENT_URL)

	def test_ntfy_utf8_message(self):
		for show_link in (0, 1):
			with (
				self.subTest(show_link=show_link),
				patch("requests.post", return_value=Mock(ok=True)) as post,
			):
				params = self._make_webhook("Ntfy", show_link)
				params.send("Notification reçue", "User", REFERENCE_NAME)
				post.assert_called_once_with(
					params.webhook_url,
					data="Notification reçue".encode(),
					headers={"Click": DOCUMENT_URL} if show_link else {},
					timeout=10,
				)

	def test_http_errors(self):
		for service, expected in (
			("Slack", "404: Channel not found"),
			("Google Chat", "404: Not Found"),
			("Matrix (Hookshot)", "404: Not Found"),
			("Ntfy", "404: Not Found"),
		):
			with (
				self.subTest(service=service),
				set_user(self.user_name),
				patch("requests.post", return_value=Mock(ok=False, status_code=404, text="Not Found")),
				self.assertRaisesRegex(WebhookDeliveryError, expected),
			):
				self._make_webhook(service).send("Test", "User", REFERENCE_NAME)

	def test_unknown_http_error(self):
		with (
			patch("requests.post", return_value=Mock(ok=False, status_code=502, text="Bad Gateway")),
			self.assertRaisesRegex(WebhookDeliveryError, "502: Bad Gateway"),
		):
			self._make_webhook().send("Test", "User", REFERENCE_NAME)

	def test_transport_errors_are_wrapped(self):
		for service in ("Slack", "Ntfy", "Matrix (Hookshot)"):
			for error_type in (requests.Timeout, requests.ConnectionError, requests.RequestException):
				error = error_type("Transport failure")
				with (
					self.subTest(service=service, error_type=error_type),
					set_user(self.user_name),
					patch("requests.post", side_effect=error),
					self.assertRaisesRegex(
						WebhookDeliveryError, "Unable to deliver the webhook notification."
					) as raised,
				):
					self._make_webhook(service).send("Test", "User", REFERENCE_NAME)
				self.assertIs(raised.exception.__cause__, error)
				self.assertIsInstance(raised.exception, frappe.ValidationError)

	def test_payload_errors_are_not_wrapped(self):
		for service in ("Slack", "Ntfy", "Matrix (Hookshot)"):
			for error_type in (requests.RequestException, frappe.ValidationError, RuntimeError):
				error = error_type("Payload failure")
				with (
					self.subTest(service=service, error_type=error_type),
					set_user(self.user_name),
					patch.object(
						SERVICE_CLASSES[service], "doc_url", new_callable=PropertyMock, side_effect=error
					),
					patch("requests.post") as post,
					self.assertRaises(error_type) as raised,
				):
					self._make_webhook(service).send("Test", "User", REFERENCE_NAME)
				self.assertIs(raised.exception, error)
				post.assert_not_called()

	def test_discord_truncation(self):
		for service in ("Discord", "Raven"):
			with (
				self.subTest(service=service),
				patch("requests.post", return_value=Mock(ok=True)) as post,
				patch.object(frappe, "log_error") as log_error,
			):
				self._make_webhook(service).send("x" * 2001, "User", REFERENCE_NAME)
				self.assertEqual(post.call_args.kwargs["json"]["content"], "x" * 1997 + "...")
				log_error.assert_called_once()
				self.assertIn("truncated", log_error.call_args.kwargs["message"])

	def test_discord_message_at_limit(self):
		with (
			patch("requests.post", return_value=Mock(ok=True)) as post,
			patch.object(frappe, "log_error") as log,
		):
			self._make_webhook("Discord").send("x" * 2000, "User", REFERENCE_NAME)
			self.assertEqual(post.call_args.kwargs["json"]["content"], "x" * 2000)
			log.assert_not_called()

	def test_discord_default_logo(self):
		self.website_settings["app_logo"] = None
		with patch("requests.post", return_value=Mock(ok=True)) as post:
			self._make_webhook("Discord").send("Test", "User", REFERENCE_NAME)
			self.assertEqual(
				post.call_args.kwargs["json"]["avatar_url"],
				f"{TEST_SITE}/assets/frappe/images/frappe-logo.png",
			)

	def test_invalid_url(self):
		for url in ("not a url", "ftp://example.com/hook", "https://", "https:hook"):
			with self.subTest(url=url), self.assertRaises(frappe.ValidationError):
				params = self._make_webhook()
				params.webhook_url = url
				params.insert()

	def test_test_message_permissions(self):
		params = self._make_webhook().insert()
		with set_user(self.user_name), patch("requests.post") as post:
			self.assertFalse(frappe.has_permission("Notification Webhook URL", "read", doc=params))
			with self.assertRaises(frappe.PermissionError):
				params.send_test_message("Test", "User", self.user_name)
			post.assert_not_called()

	def test_test_message_as_system_manager(self):
		self.user.add_roles("System Manager")
		params = self._make_webhook().insert()
		with set_user(self.user_name), patch("requests.post", return_value=Mock(ok=True)):
			self.assertEqual(params.send_test_message("Test", "User", self.user_name), "success")

	def test_test_message_failure(self):
		self.user.add_roles("System Manager")
		params = self._make_webhook().insert()
		with (
			set_user(self.user_name),
			patch("requests.post", return_value=Mock(ok=False, status_code=404, text="Not Found")),
			self.assertRaisesRegex(WebhookDeliveryError, "404: Channel not found"),
		):
			params.send_test_message("Test", "User", self.user_name)

	def test_notification_sends_rendered_message_without_recipients(self):
		params = self._make_webhook(show_document_link=0).insert()
		notification = self._make_notification(params).insert()
		with set_user(self.user_name), patch("requests.post", return_value=Mock(ok=True)) as post:
			notification.send(self.user)
			post.assert_called_once_with(params.webhook_url, json={"text": "Hello Webhook Test"}, timeout=10)

	def test_notification_logs_delivery_failure_and_sends_system_notification(self):
		for service in ("Slack", "Ntfy", "Matrix (Hookshot)"):
			for result, error_message in (
				(Mock(ok=False, status_code=502, text="Bad Gateway"), "502: Bad Gateway"),
				(requests.Timeout("Request timed out"), "Request timed out"),
				(requests.ConnectionError("Connection failed"), "Connection failed"),
			):
				params = self._make_webhook(service).insert()
				notification = self._make_notification(params)
				notification.send_system_notification = 1
				with (
					self.subTest(service=service, error_message=error_message),
					set_user(self.user_name),
					patch("requests.post") as post,
					patch.object(notification, "log_error") as log_error,
					patch.object(notification, "create_system_notification") as system_notification,
				):
					if isinstance(result, requests.RequestException):
						post.side_effect = result
					else:
						post.return_value = result
					notification.send(self.user)
				post.assert_called_once()
				log_error.assert_called_once()
				self.assertEqual(log_error.call_args.kwargs["title"], "Failed to send Notification")
				self.assertIn("WebhookDeliveryError", log_error.call_args.kwargs["message"])
				self.assertIn(error_message, log_error.call_args.kwargs["message"])
				system_notification.assert_called_once()

	def test_notification_missing_webhook_is_not_swallowed(self):
		notification = self._make_notification(self._make_webhook())
		notification.notification_webhook_url = f"Missing webhook {frappe.generate_hash(length=8)}"
		with (
			set_user(self.user_name),
			patch("requests.post") as post,
			patch.object(notification, "log_error") as log_error,
			self.assertRaises(frappe.DoesNotExistError),
		):
			notification.send_webhook_message(self.user, {"doc": self.user})
		post.assert_not_called()
		log_error.assert_not_called()

	def test_notification_rendering_error_is_not_swallowed(self):
		params = self._make_webhook().insert()
		notification = self._make_notification(params)
		error = frappe.ValidationError("Invalid template")
		with (
			set_user(self.user_name),
			patch.object(frappe, "render_template", side_effect=error),
			patch("requests.post") as post,
			patch.object(notification, "log_error") as log_error,
			self.assertRaises(frappe.ValidationError) as raised,
		):
			notification.send_webhook_message(self.user, {"doc": self.user})
		self.assertIs(raised.exception, error)
		post.assert_not_called()
		log_error.assert_not_called()

	def test_notification_unrelated_sending_errors_are_not_swallowed(self):
		params = self._make_webhook().insert()
		notification = self._make_notification(params)
		for error_type in (RuntimeError, frappe.ValidationError, frappe.DoesNotExistError):
			error = error_type("Unrelated failure")
			with (
				self.subTest(error_type=error_type),
				set_user(self.user_name),
				patch("requests.post", side_effect=error),
				patch.object(notification, "log_error") as log_error,
				self.assertRaises(error_type) as raised,
			):
				notification.send_webhook_message(self.user, {"doc": self.user})
			self.assertIs(raised.exception, error)
			log_error.assert_not_called()

	def test_repeated_legacy_notification_imports_keep_sending(self):
		self.user.add_roles("System Manager")
		params = self._make_webhook(show_document_link=0).insert()
		notification = self._make_notification(params).insert()
		legacy = notification.as_dict()
		legacy["channel"] = "Slack"
		legacy["slack_webhook_url"] = legacy.pop("notification_webhook_url")

		with set_user(self.user_name):
			for attempt in range(2):
				with self.subTest(attempt=attempt):
					docdict = deepcopy(legacy)
					import_doc(docdict)
					imported = Notification.docs.get(notification.name)
					self.assertEqual(imported.channel, "Webhook")
					self.assertEqual(imported.notification_webhook_url, params.name)
					self.assertNotIn("slack_webhook_url", docdict)
					with patch("requests.post", return_value=Mock(ok=True)) as post:
						imported.send(self.user)
						post.assert_called_once_with(
							params.webhook_url, json={"text": "Hello Webhook Test"}, timeout=10
						)

	def test_legacy_notification_import_preserves_migrated_target(self):
		self.user.add_roles("System Manager")
		legacy_target = self._make_webhook().insert()
		migrated_target = self._make_webhook("Discord").insert()
		notification = self._make_notification(migrated_target).insert()
		legacy = notification.as_dict()
		legacy["channel"] = "Slack"
		legacy["slack_webhook_url"] = legacy_target.name

		with set_user(self.user_name):
			for attempt in range(2):
				with self.subTest(attempt=attempt):
					docdict = deepcopy(legacy)
					import_doc(docdict)
					imported = Notification.docs.get(notification.name)
					self.assertEqual(imported.channel, "Webhook")
					self.assertEqual(imported.notification_webhook_url, migrated_target.name)
					self.assertNotIn("slack_webhook_url", docdict)

	def test_notification_import_leaves_other_channels_unchanged(self):
		with set_user(self.user_name):
			for channel in ("Email", "Webhook", None):
				with self.subTest(channel=channel):
					docdict = {"channel": channel, "slack_webhook_url": "Legacy webhook"}
					Notification.prepare_for_import(docdict)
					self.assertEqual(docdict, {"channel": channel, "slack_webhook_url": "Legacy webhook"})

	def test_notification_webhook_is_required(self):
		notification = self._make_notification(self._make_webhook())
		with self.assertRaises(frappe.MandatoryError):
			notification.insert()
