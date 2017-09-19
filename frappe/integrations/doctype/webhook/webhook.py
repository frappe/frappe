# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json, requests
from frappe import _
from frappe.model.document import Document
from six.moves.urllib.parse import urlparse

class Webhook(Document):
	def autoname(self):
		self.name = self.webhook_doctype + "-" + self.webhook_docevent
	def validate(self):
		self.validate_docevent()
		self.validate_request_url()
		self.validate_repeating_fields()
	def validate_docevent(self):
		if self.webhook_doctype:
			is_submittable = frappe.get_value("DocType", self.webhook_doctype, "is_submittable")
			if not is_submittable and self.webhook_docevent in ["on_submit", "on_cancel", "on_update_after_submit"]:
				frappe.throw(_("DocType must be Submittable for the selected Doc Event"))
	def validate_request_url(self):
		try:
			request_url = urlparse(self.request_url).netloc
			if not request_url:
				raise frappe.ValidationError
		except Exception as e:
			frappe.throw(_("Check Request URL"), exc=e)
	def validate_repeating_fields(self):
		"""Error when Same Field is entered multiple times in webhook_data"""
		webhook_data = []
		for entry in self.webhook_data:
			webhook_data.append(entry.fieldname)

		if len(webhook_data)!= len(set(webhook_data)):
			frappe.throw(_("Same Field is entered more than once"))
	def request(self, doc):
		headers = {}
		data = {}
		if self.webhook_headers:
			for h in self.webhook_headers:
				if h.get("key") and h.get("value"):
					headers[h.get("key")] = h.get("value")
		if self.webhook_data:
			for k, v in doc.as_dict().items():
				for w in self.webhook_data:
					if k == w.fieldname:
						data[w.key] = v
		r = requests.post(self.request_url, data=json.dumps(data), headers=headers, timeout=5)
		frappe.logger().debug({"webhook_success":r.text})

def enqueue_webhook(doc, webhook):
	webhook = frappe.get_doc("Webhook", webhook.get("name"))
	try:
		webhook.request(doc)
	except Exception as e:
		frappe.throw(_("Error in Webhook"), exc=e)

def webhook_request(doc, webhook):
	frappe.enqueue('frappe.integrations.doctype.webhook.webhook.enqueue_webhook', doc=doc, webhook=webhook)
