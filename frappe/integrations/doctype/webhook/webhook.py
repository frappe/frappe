# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import datetime
import json
from time import sleep

import requests
from six.moves.urllib.parse import urlparse

import frappe
from frappe import _
from frappe.model.document import Document


class Webhook(Document):
	def autoname(self):
		self.name = self.webhook_doctype + "-" + self.webhook_docevent

	def validate(self):
		self.validate_docevent()
		self.validate_condition()
		self.validate_request_url()
		self.validate_repeating_fields()

	def on_update(self):
		frappe.cache().delete_value('webhooks')

	def validate_docevent(self):
		if self.webhook_doctype:
			is_submittable = frappe.get_value("DocType", self.webhook_doctype, "is_submittable")
			if not is_submittable and self.webhook_docevent in ["on_submit", "on_cancel", "on_update_after_submit"]:
				frappe.throw(_("DocType must be Submittable for the selected Doc Event"))

	def validate_condition(self):
		temp_doc = frappe.new_doc(self.webhook_doctype)
		if self.condition:
			try:
				frappe.safe_eval(self.condition, eval_locals=get_context(temp_doc))
			except Exception as e:
				frappe.throw(_(e))

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

		if len(webhook_data) != len(set(webhook_data)):
			frappe.throw(_("Same Field is entered more than once"))


def get_context(doc):
	return {"doc": doc, "utils": frappe.utils}


def enqueue_webhook(doc, webhook):
	webhook = frappe.get_doc("Webhook", webhook.get("name"))
	headers = {}
	data = {}
	if webhook.webhook_headers:
		for h in webhook.webhook_headers:
			if h.get("key") and h.get("value"):
				headers[h.get("key")] = h.get("value")
	if webhook.webhook_data:
		for w in webhook.webhook_data:
			for k, v in doc.as_dict().items():
				if k == w.fieldname:
					if isinstance(v, datetime.datetime):
						v = frappe.utils.get_datetime_str(v)
					data[w.key] = v
	for i in range(3):
		try:
			r = requests.post(webhook.request_url, data=json.dumps(data), headers=headers, timeout=5)
			r.raise_for_status()
			frappe.logger().debug({"webhook_success": r.text})
			break
		except Exception as e:
			frappe.logger().debug({"webhook_error": e, "try": i + 1})
			sleep(3 * i + 1)
			if i != 2:
				continue
			else:
				raise e
