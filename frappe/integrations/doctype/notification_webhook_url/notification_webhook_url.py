# Copyright (c) 2018, Frappe Technologies and contributors
# License: MIT. See LICENSE

from urllib.parse import urlparse

import requests

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_url, get_url_to_form, validate_url


class WebhookDeliveryError(frappe.ValidationError):
	"""A transport failure or unsuccessful response from a notification webhook."""


class NotificationWebhookParametersBase:
	def __init__(
		self,
		params: "NotificationWebhookURL",
		message: str,
		reference_doctype: str,
		reference_name: str,
	) -> None:
		self.params = params
		self.message = message
		self.reference_doctype = reference_doctype
		self.reference_name = reference_name

	@property
	def doc_url(self) -> str:
		return get_url_to_form(self.reference_doctype, self.reference_name)

	def build_data(self) -> dict:
		data = {"text": self.message}
		if self.params.show_document_link:
			data["text"] = f"{self.message}\n<{self.doc_url}|{_('Document link')}>"
		return data

	def send(self) -> requests.Response:
		data = self.build_data()
		try:
			response = requests.post(self.params.webhook_url, json=data, timeout=10)
		except requests.RequestException as exc:
			raise WebhookDeliveryError(_("Unable to deliver the webhook notification.")) from exc
		if not response.ok:
			message = self.get_error_messages().get(response.status_code)
			frappe.throw(message or f"{response.status_code}: {response.text}", exc=WebhookDeliveryError)
		return response

	def get_error_messages(self) -> dict[int, str]:
		return {}


class SlackParameters(NotificationWebhookParametersBase):
	def build_data(self) -> dict:
		data: dict = {"text": self.message}
		if self.params.show_document_link:
			data["attachments"] = [
				{
					"fallback": _("See the document at {0}").format(self.doc_url),
					"actions": [
						{
							"type": "button",
							"text": _("Go to the document"),
							"url": self.doc_url,
							"style": "primary",
						}
					],
				}
			]
		return data

	def get_error_messages(self) -> dict[int, str]:
		return {
			400: _("400: Invalid Payload or User not found"),
			403: _("403: Action Prohibited"),
			404: _("404: Channel not found"),
			410: _("410: The Channel is Archived"),
			500: _("500: Rollup Error, Slack seems to be down"),
		}


class RocketChatParameters(NotificationWebhookParametersBase):
	def build_data(self) -> dict:
		data: dict = {"text": self.message}
		if self.params.show_document_link:
			data["attachments"] = [{"title": _("Document link"), "title_link": self.doc_url}]
		return data


class GoogleChatParameters(NotificationWebhookParametersBase):
	pass


class MatrixHookshotParameters(NotificationWebhookParametersBase):
	"""Format messages for Matrix Hookshot's inbound webhooks."""

	def build_data(self) -> dict:
		text = self.message
		if self.params.show_document_link:
			text += f"\n\n[{_('Document link')}]({self.doc_url})"
		return {"text": text}


class MattermostParameters(NotificationWebhookParametersBase):
	pass


class TeamsParameters(NotificationWebhookParametersBase):
	"""Format messages as Adaptive Cards for Teams incoming webhooks."""

	def build_data(self) -> dict:
		card = {
			"$schema": "https://adaptivecards.io/schemas/adaptive-card.json",
			"type": "AdaptiveCard",
			"version": "1.2",
			"body": [{"type": "TextBlock", "text": self.message, "wrap": True}],
		}
		if self.params.show_document_link:
			card["actions"] = [{"type": "Action.OpenUrl", "title": _("Document link"), "url": self.doc_url}]
		return {
			"type": "message",
			"attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": card}],
		}


class DiscordParameters(NotificationWebhookParametersBase):
	def build_data(self) -> dict:
		app_logo = frappe.get_website_settings("app_logo") or "/assets/frappe/images/frappe-logo.png"
		content = self.message
		if len(content) > 2000:
			frappe.log_error(
				title=_("Notification Webhook URL (Discord)"),
				message=_("Discord message truncated from {0} to 2000 characters").format(len(content)),
			)
			content = content[:1997] + "..."
		data: dict = {
			"content": content,
			"username": frappe.get_website_settings("app_name"),
			"avatar_url": get_url(app_logo),
		}
		if self.params.show_document_link:
			data["embeds"] = [{"title": _("Document link"), "url": self.doc_url}]
		return data


class NtfyParameters(NotificationWebhookParametersBase):
	def send(self) -> requests.Response:
		headers = {"Click": self.doc_url} if self.params.show_document_link else {}
		data = self.message.encode("utf-8")
		try:
			response = requests.post(self.params.webhook_url, data=data, headers=headers, timeout=10)
		except requests.RequestException as exc:
			raise WebhookDeliveryError(_("Unable to deliver the webhook notification.")) from exc
		if not response.ok:
			frappe.throw(f"{response.status_code}: {response.text}", exc=WebhookDeliveryError)
		return response


SERVICE_CLASSES: dict[str, type[NotificationWebhookParametersBase]] = {
	"Google Chat": GoogleChatParameters,
	"Matrix (Hookshot)": MatrixHookshotParameters,
	"Mattermost": MattermostParameters,
	"Rocket.Chat": RocketChatParameters,
	"Slack": SlackParameters,
	"Teams": TeamsParameters,
	"Discord": DiscordParameters,
	"Ntfy": NtfyParameters,
	"Raven": DiscordParameters,
}


class NotificationWebhookURL(Document):
	"""Send document notifications using a destination service's webhook URL."""

	_DOCTYPE_NAME = "Notification Webhook URL"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		service: DF.Literal[
			"Google Chat",
			"Matrix (Hookshot)",
			"Mattermost",
			"Rocket.Chat",
			"Slack",
			"Teams",
			"Discord",
			"Ntfy",
			"Raven",
		]
		show_document_link: DF.Check
		webhook_name: DF.Data
		webhook_url: DF.SmallText
	# end: auto-generated types

	def validate(self) -> None:
		if self.webhook_url:
			validate_url(self.webhook_url, throw=True, valid_schemes=("http", "https"))
			if not urlparse(self.webhook_url).netloc:
				frappe.throw(_("'{0}' is not a valid URL").format(frappe.bold(self.webhook_url)))

	def send(self, message: str, reference_doctype: str, reference_name: str) -> str:
		"""Send a rendered message and raise on delivery failure."""
		service = SERVICE_CLASSES[self.service](self, message, reference_doctype, reference_name)
		service.send()
		return "success"

	@frappe.whitelist()
	def send_test_message(self, message: str, reference_doctype: str, reference_name: str) -> str:
		"""Send a test message using a webhook managed by the current user."""
		frappe.only_for("System Manager")
		self.check_permission("write")
		return self.send(message, reference_doctype, reference_name)
