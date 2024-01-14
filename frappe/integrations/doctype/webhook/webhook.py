# Copyright (c) 2017, Frappe Technologies and contributors
# License: MIT. See LICENSE

import base64
import hashlib
import hmac
import json
from time import sleep
from urllib.parse import urlparse

import requests

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.jinja import validate_template
from frappe.utils.safe_exec import get_safe_globals

WEBHOOK_SECRET_HEADER = "X-Frappe-Webhook-Signature"


class Webhook(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.integrations.doctype.webhook_data.webhook_data import WebhookData
		from frappe.integrations.doctype.webhook_header.webhook_header import WebhookHeader
		from frappe.types import DF

		condition: DF.SmallText | None
		enable_security: DF.Check
		enabled: DF.Check
		is_dynamic_url: DF.Check
		meets_condition: DF.Data | None
		preview_document: DF.DynamicLink | None
		preview_request_body: DF.Code | None
		request_method: DF.Literal["POST", "PUT", "DELETE"]
		request_structure: DF.Literal["", "Form URL-Encoded", "JSON"]
		request_url: DF.Data
		timeout: DF.Int
		webhook_data: DF.Table[WebhookData]
		webhook_docevent: DF.Literal[
			"after_insert",
			"on_update",
			"on_submit",
			"on_cancel",
			"on_trash",
			"on_update_after_submit",
			"on_change",
		]
		webhook_doctype: DF.Link
		webhook_headers: DF.Table[WebhookHeader]
		webhook_json: DF.Code | None
		webhook_secret: DF.Password | None
	# end: auto-generated types
	def validate(self):
		self.validate_docevent()
		self.validate_condition()
		self.validate_request_url()
		self.validate_request_body()
		self.validate_repeating_fields()
		self.validate_secret()
		self.preview_document = None

	def on_update(self):
		frappe.cache.delete_value("webhooks")

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
		webhook_data = [entry.fieldname for entry in self.webhook_data]
		if len(webhook_data) != len(set(webhook_data)):
			frappe.throw(_("Same Field is entered more than once"))

	def validate_secret(self):
		if self.enable_security:
			try:
				self.get_password("webhook_secret", False).encode("utf8")
			except Exception:
				frappe.throw(_("Invalid Webhook Secret"))

	@frappe.whitelist()
	def generate_preview(self):
		# This function doesn't need to do anything specific as virtual fields
		# get evaluated automatically.
		pass

	@property
	def meets_condition(self):
		if not self.condition:
			return _("Yes")

		if not (self.preview_document and self.webhook_doctype):
			return _("Select a document to check if it meets conditions.")

		try:
			doc = frappe.get_cached_doc(self.webhook_doctype, self.preview_document)
			met_condition = frappe.safe_eval(self.condition, eval_locals=get_context(doc))
		except Exception as e:
			return _("Failed to evaluate conditions: {}").format(e)
		return _("Yes") if met_condition else _("No")

	@property
	def preview_request_body(self):
		if not (self.preview_document and self.webhook_doctype):
			return _("Select a document to preview request data")

		try:
			doc = frappe.get_cached_doc(self.webhook_doctype, self.preview_document)
			return frappe.as_json(get_webhook_data(doc, self))
		except Exception as e:
			return _("Failed to compute request body: {}").format(e)


def get_context(doc):
	return {"doc": doc, "utils": get_safe_globals().get("frappe").get("utils")}


def enqueue_webhook(doc, webhook) -> None:
	request_url = headers = data = None
	try:
		webhook: Webhook = frappe.get_doc("Webhook", webhook.get("name"))
		request_url = webhook.request_url
		if webhook.is_dynamic_url:
			request_url = frappe.render_template(webhook.request_url, get_context(doc))
		headers = get_webhook_headers(doc, webhook)
		data = get_webhook_data(doc, webhook)

	except Exception as e:
		frappe.logger().debug({"enqueue_webhook_error": e})
		log_request(webhook.name, doc.name, request_url, headers, data)
		return

	for i in range(3):
		try:
			r = requests.request(
				method=webhook.request_method,
				url=request_url,
				data=json.dumps(data, default=str),
				headers=headers,
				timeout=webhook.timeout or 5,
			)
			r.raise_for_status()
			frappe.logger().debug({"webhook_success": r.text})
			log_request(webhook.name, doc.name, request_url, headers, data, r)
			break

		except requests.exceptions.ReadTimeout as e:
			frappe.logger().debug({"webhook_error": e, "try": i + 1})
			log_request(webhook.name, doc.name, request_url, headers, data)

		except Exception as e:
			frappe.logger().debug({"webhook_error": e, "try": i + 1})
			log_request(webhook.name, doc.name, request_url, headers, data, r)
			sleep(3 * i + 1)
			if i != 2:
				continue


def log_request(
	webhook: str,
	docname: str,
	url: str,
	headers: dict,
	data: dict,
	res: requests.Response | None = None,
):
	request_log = frappe.get_doc(
		{
			"doctype": "Webhook Request Log",
			"webhook": webhook,
			"reference_document": docname,
			"user": frappe.session.user if frappe.session.user else None,
			"url": url,
			"headers": frappe.as_json(headers) if headers else None,
			"data": frappe.as_json(data) if data else None,
			"response": res and res.text,
			"error": frappe.get_traceback(),
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
