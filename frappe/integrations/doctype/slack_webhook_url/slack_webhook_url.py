# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import get_url_to_form
from frappe import _
import requests
import json

class SlackWebhookURL(Document):
	pass

def send_slack_message(webhook_url, message, reference_doctype, reference_name):
	slack_url = frappe.db.get_value("Slack Webhook URL", webhook_url, "webhook_url")
	doc_url = get_url_to_form(reference_doctype, reference_name)
	attachments = [
		{
			"fallback": _("See the document at {0}").format(doc_url),
			"actions": [
				{
				"type": "button",
				"text": _("Go to the document"),
				"url": doc_url,
				"style": "primary"
				}
			]
		}
	]
	data = {"text": message, "attachments": attachments}
	r = requests.post(slack_url, data=json.dumps(data))


	if r.ok == True:
		return 'success'

	elif r.ok == False:
		status = r.status_code
		if status == 400:
			message = _("400 - Invalid payload or user not found")
		elif status == 403:
			message = _("403 - Action Prohibited")
		elif status == 404:
			message = _("404 - Channel not found")
		elif status == 410:
			message = _("410 - The Channel is Archived")
		elif status == 500:
			message = _("500 - Rollup error, slack seems down")
		else:
			message = r.status_code

		frappe.log_error(message, _('Slack Webhook Error'))
		return 'error'
