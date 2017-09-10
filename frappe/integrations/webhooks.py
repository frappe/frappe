# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, requests
from frappe import _

# Doc Events Webhook
def doc_event_webhook(doc, method=None, *args, **kwargs):
	headers = {}
	filters = {
		"webhook_doctype": doc.get("doctype"),
		"webhook_docevent": method
	}
	webhooks = frappe.get_all("Webhook", filters=filters)
	webhook = frappe.get_doc("Webhook", webhooks[0].get("name")) if webhooks and len(webhooks) > 0 else None
	if webhook:
		if webhook.webhook_headers:
			for h in webhook.webhook_headers:
				if h.get("key") and h.get("value"):
					headers[h.get("key")] = h.get("value")
		try:
			r = requests.post(webhook.request_url, data=doc.as_json(), headers=headers, timeout=5)
			frappe.logger().debug({"webhook_success":r.text, "webhook": webhook.as_json()})
		except Exception as e:
			frappe.logger().debug({"webhook_error":r.text, "webhook": webhook.as_json()})
			frappe.throw(_("Unable to make request"))
