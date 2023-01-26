# Copyright (c) 2018, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json

import requests

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_url_to_form

error_messages = {
	400: "400: Invalid Payload or User not found",
	403: "403: Action Prohibited",
	404: "404: Channel not found",
	410: "410: The Channel is Archived",
	500: "500: Rollup Error, Slack seems to be down",
}


class SlackWebhookURL(Document):
	pass


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
