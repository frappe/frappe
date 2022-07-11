# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import base64
import datetime
import hashlib
import hmac
import json
from time import sleep

import requests
from six.moves.urllib.parse import urlparse

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.jinja import validate_template
from frappe.utils.safe_exec import get_safe_globals

WEBHOOK_SECRET_HEADER = "X-Frappe-Webhook-Signature"


class Webhook(Document):
	def validate(self):
		self.validate_docevent()
		self.validate_condition()
		self.validate_request_url()
		self.validate_request_body()
		self.validate_repeating_fields()

	def on_update(self):
		frappe.cache().delete_value("webhooks")

	def validate_docevent(self):
		if self.webhook_doctype:
			is_submittable = frappe.get_value("DocType", self.webhook_doctype, "is_submittable")
			if not is_submittable and self.webhook_docevent in [
				"on_submit",
				"on_cancel",
				"on_update_after_submit",
			]:
				frappe.throw(_("DocType must be Submittable for the selected Doc Event"))

	def validate_condition(self):
		temp_doc = frappe.new_doc(self.webhook_doctype)
		if self.condition:
			try:
				frappe.safe_eval(self.condition, eval_locals=get_context(temp_doc))
			except Exception as e:
				frappe.throw(_("Invalid Condition: {}").format(e))

	def validate_request_url(self):
		try:
			request_url = urlparse(self.request_url).netloc
			if not request_url:
				raise frappe.ValidationError
		except Exception as e:
			frappe.throw(_("Check Request URL"), exc=e)

	def validate_request_body(self):
		if self.request_structure:
			if self.request_structure == "Form URL-Encoded":
				self.webhook_json = None
			elif self.request_structure == "JSON":
				validate_template(self.webhook_json)
				self.webhook_data = []

	def validate_repeating_fields(self):
		"""Error when Same Field is entered multiple times in webhook_data"""
		webhook_data = []
		for entry in self.webhook_data:
			webhook_data.append(entry.fieldname)

		if len(webhook_data) != len(set(webhook_data)):
			frappe.throw(_("Same Field is entered more than once"))


def get_context(doc):
	return {"doc": doc, "utils": get_safe_globals().get("frappe").get("utils")}


def enqueue_webhook(doc, webhook):
	webhook = frappe.get_doc("Webhook", webhook.get("name"))
	headers = get_webhook_headers(doc, webhook)
	data = get_webhook_data(doc, webhook)

	for i in range(3):
		try:
			r = requests.request(
				method=webhook.request_method,
				url=webhook.request_url,
				data=json.dumps(data, default=str),
				headers=headers,
				timeout=5,
			)
			r.raise_for_status()
			frappe.logger().debug({"webhook_success": r.text})
			log_request(webhook.request_url, headers, data, r)
			break
		except Exception as e:
			frappe.logger().debug({"webhook_error": e, "try": i + 1})
			log_request(webhook.request_url, headers, data, r)
			sleep(3 * i + 1)
			if i != 2:
				continue
			else:
				raise e


def log_request(url, headers, data, res):
	request_log = frappe.get_doc(
		{
			"doctype": "Webhook Request Log",
			"user": frappe.session.user if frappe.session.user else None,
			"url": url,
			"headers": frappe.as_json(headers) if headers else None,
			"data": frappe.as_json(data) if data else None,
			"response": frappe.as_json(res.json()) if res else None,
		}
	)

	request_log.save(ignore_permissions=True)


def get_webhook_headers(doc, webhook):
	headers = {}

	if webhook.enable_security:
		data = get_webhook_data(doc, webhook)
		signature = base64.b64encode(
			hmac.new(
				webhook.get_password("webhook_secret").encode("utf8"),
				json.dumps(data).encode("utf8"),
				hashlib.sha256,
			).digest()
		)
		headers[WEBHOOK_SECRET_HEADER] = signature

	if webhook.webhook_headers:
		for h in webhook.webhook_headers:
			if h.get("key") and h.get("value"):
				headers[h.get("key")] = h.get("value")

	return headers


def get_webhook_data(doc, webhook):
	data = {}
	doc = doc.as_dict(convert_dates_to_str=True)

	if webhook.webhook_data:
		data = {w.key: doc.get(w.fieldname) for w in webhook.webhook_data}
	elif webhook.webhook_json:
		data = frappe.render_template(webhook.webhook_json, get_context(doc))
		data = json.loads(data)

	return data
