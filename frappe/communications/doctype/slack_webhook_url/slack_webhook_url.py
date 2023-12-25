# Copyright (c) 2018, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
from typing import TYPE_CHECKING

import requests

import frappe
from frappe import _
from frappe.communications.interfaces import NotificationHandler, OutgoingCommunicationHandler
from frappe.model.document import Document
from frappe.utils import get_url_to_form

if TYPE_CHECKING:
	from frappe.communications.doctype.communication.communication import Communication
	from frappe.communications.doctype.notification.notification import Notification

error_messages = {
	400: "400: Invalid Payload or User not found",
	403: "403: Action Prohibited",
	404: "404: Channel not found",
	410: "410: The Channel is Archived",
	500: "500: Rollup Error, Slack seems to be down",
}


class SlackWebhookURL(Document, OutgoingCommunicationHandler, NotificationHandler):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		show_document_link: DF.Check
		webhook_name: DF.Data
		webhook_url: DF.Data
	# end: auto-generated types

	_communication_medium = "Chat"

	def _validate_communication(self, comm: Communication):
		comm.recipients = _("Slack Channel: {}").format(comm.recipients)

	def _send_implementation(self, comm: Communication):
		res = send_slack_message(self.name, comm.content)

		if res == "success":
			return comm.recipients
		return []

	def _get_notification_recipients(
		self, notification: Notification, doc: Document, context: dict
	) -> list[str]:
		"""slack channels, as currently implemented, don't implement specific recipients, we render a channel recipient for display"""
		return [_("Slack Channel: {}").format(self.name)]

	def _get_notification_sender(
		self, notification: Notification, doc: Document, context: dict
	) -> str:
		return None

	def _log_notification(self, notification: Notification, doc: Document, context: dict) -> bool:
		if doc.docname == "Communication":
			return False  # Don't log a notification from an already existing communication again
		return True


def send_slack_message(webhook_url, message, reference_doctype, reference_name):
	data = {"text": message, "attachments": []}

	slack_url, show_link = frappe.db.get_value(
		"Slack Webhook URL", webhook_url, ["webhook_url", "show_document_link"]
	)

	if show_link:
		doc_url = get_url_to_form(reference_doctype, reference_name)
		link_to_doc = {
			"fallback": _("See the document at {0}").format(doc_url),
			"actions": [
				{
					"type": "button",
					"text": _("Go to the document"),
					"url": doc_url,
					"style": "primary",
				}
			],
		}
		data["attachments"].append(link_to_doc)

	r = requests.post(slack_url, data=json.dumps(data))

	if not r.ok:
		message = error_messages.get(r.status_code, r.status_code)
		frappe.log_error(message, _("Slack Webhook Error"))
		return "error"

	return "success"
