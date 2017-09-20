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
		r.raise_for_status()
		frappe.logger().debug({"webhook_success":r.text})

def enqueue_webhook(doc, webhook):
	webhook = frappe.get_doc("Webhook", webhook.get("name"))
	try:
		webhook.request(doc)
	except Exception as e:
		frappe.throw(_("Error in Webhook"), exc=e)

def run_webhooks(doc, method):
	'''Run webhooks for this method'''
	if frappe.flags.in_import or frappe.flags.in_patch or frappe.flags.in_install:
		return

	if not getattr(frappe.local, 'webhooks_executed', None):
		frappe.local.webhooks_executed = []

	if doc.flags.webhooks == None:
		webhooks = frappe.cache().hget('webhooks', doc.doctype)
		if webhooks==None:
			webhooks = frappe.get_all('Webhook',
				fields=["name", "webhook_docevent"])
			frappe.cache().hset('webhooks', doc.doctype, webhooks)
		doc.flags.webhooks = webhooks

	if not doc.flags.webhooks:
		return

	def _webhook_request(webhook):
		if not webhook.name in frappe.local.webhooks_executed:
			frappe.enqueue("frappe.integrations.doctype.webhook.webhook.enqueue_webhook", doc=doc, webhook=webhook)
			frappe.local.webhooks_executed.append(webhook.name)

	event_list = ["on_update", "after_insert", "on_submit", "on_cancel", "on_trash"]

	if not doc.flags.in_insert:
		# value change is not applicable in insert
		event_list.append('on_change')
		event_list.append('before_update_after_submit')

	for webhook in doc.flags.webhooks:
		event = method if method in event_list else None
		if event and webhook.webhook_docevent == event:
			_webhook_request(webhook)
