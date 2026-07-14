# Copyright (c) 2017, Frappe Technologies and contributors
# License: MIT. See LICENSE

import base64
import hashlib
import hmac
import json
from urllib.parse import urlparse

import requests

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, cint, now_datetime
from frappe.utils.background_jobs import get_queues_timeout, is_job_enqueued
from frappe.utils.jinja import validate_template
from frappe.utils.safe_exec import get_safe_globals

WEBHOOK_SECRET_HEADER = "X-Frappe-Webhook-Signature"

RETRY_SCHEDULE = [5 * 60, 30 * 60, 2 * 3600, 5 * 3600, 10 * 3600, 10 * 3600]

RETRY_BATCH_SIZE = 100


class Webhook(Document):
	_DOCTYPE_NAME = "Webhook"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.integrations.doctype.webhook_data.webhook_data import WebhookData
		from frappe.integrations.doctype.webhook_header.webhook_header import WebhookHeader
		from frappe.types import DF

		background_jobs_queue: DF.Autocomplete | None
		condition: DF.SmallText | None
		enable_security: DF.Check
		enabled: DF.Check
		is_dynamic_url: DF.Check
		max_retries: DF.Int
		request_method: DF.Literal["POST", "PUT", "DELETE"]
		request_structure: DF.Literal["", "Form URL-Encoded", "JSON"]
		request_url: DF.SmallText
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
			"workflow_transition",
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
		frappe.client_cache.delete_value("webhooks")

	def execute_for_doc(self, doc: Document):
		enqueue_webhook(doc, self)

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
				frappe.throw(_("Invalid Condition: {}").format(str(e)))

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
	def preview_meets_condition(self, preview_document: str):
		if not self.condition:
			return _("Yes")
		try:
			doc = frappe.get_cached_doc(self.webhook_doctype, preview_document)
			met_condition = frappe.safe_eval(self.condition, eval_locals=get_context(doc))
		except Exception as e:
			frappe.local.message_log = []
			return _("Failed to evaluate conditions: {}").format(str(e))
		return _("Yes") if met_condition else _("No")

	@frappe.whitelist()
	def preview_request_body(self, preview_document: str):
		try:
			doc = frappe.get_cached_doc(self.webhook_doctype, preview_document)
			return frappe.as_json(get_webhook_data(doc, self))
		except Exception as e:
			frappe.local.message_log = []
			return _("Failed to compute request body: {}").format(str(e))


def get_context(doc):
	return {"doc": doc, "utils": get_safe_globals().get("frappe").get("utils")}


def enqueue_webhook(doc, webhook) -> None:
	request_url = headers = data = None
	try:
		if not isinstance(webhook, Document):
			webhook: Webhook = frappe.get_doc("Webhook", webhook.get("name"))
		request_url = webhook.request_url
		if webhook.is_dynamic_url:
			request_url = frappe.render_template(webhook.request_url, get_context(doc))
		data = get_webhook_data(doc, webhook)
		headers = get_webhook_headers(doc, webhook, data=data)

	except Exception as e:
		frappe.logger().debug({"enqueue_webhook_error": e})
		log_request(webhook.name, doc.doctype, doc.name, request_url, headers, data, status="Exhausted")
		return

	res = None
	try:
		res = send_webhook_request(webhook.request_method, request_url, headers, data, webhook.timeout)
		res.raise_for_status()
		frappe.logger().debug({"webhook_success": res.text})
		log_request(webhook.name, doc.doctype, doc.name, request_url, headers, data, res, status="Delivered")

	except Exception as e:
		frappe.logger().debug({"webhook_error": e, "try": 1})

		# A workflow transition needs the webhook result now, so fail it instead of deferring a retry.
		if webhook.webhook_docevent == "workflow_transition":
			log_request(
				webhook.name, doc.doctype, doc.name, request_url, headers, data, res, status="Exhausted"
			)
			raise

		if cint(webhook.max_retries) >= 1:
			log_request(
				webhook.name,
				doc.doctype,
				doc.name,
				request_url,
				headers,
				data,
				res,
				status="Failed",
				next_retry=get_next_retry(1),
			)
		else:
			log_request(
				webhook.name, doc.doctype, doc.name, request_url, headers, data, res, status="Exhausted"
			)


def send_webhook_request(method, url, headers, data, timeout):
	return requests.request(
		method=method,
		url=url,
		data=frappe.as_json(data),
		headers=headers,
		timeout=timeout or 5,
	)


def get_next_retry(attempt: int):
	delay = RETRY_SCHEDULE[min(attempt - 1, len(RETRY_SCHEDULE) - 1)]
	return add_to_date(now_datetime(), seconds=delay)


def retry_failed_webhooks():
	"""Enqueue a delivery job for each webhook whose scheduled retry time has passed."""
	due_logs = frappe.get_all(
		"Webhook Request Log",
		filters={"status": "Failed", "next_retry": ["<=", now_datetime()]},
		fields=["name", "webhook"],
		order_by="next_retry asc",
		limit=RETRY_BATCH_SIZE,
	)

	queues = {}
	for log in due_logs:
		job_id = f"webhook_retry::{log.name}"
		if is_job_enqueued(job_id):
			continue

		if log.webhook not in queues:
			queues[log.webhook] = (
				frappe.db.get_value("Webhook", log.webhook, "background_jobs_queue") or "default"
			)

		frappe.enqueue(
			"frappe.integrations.doctype.webhook.webhook.retry_webhook_delivery",
			log_name=log.name,
			job_id=job_id,
			queue=queues[log.webhook],
			now=frappe.in_test,
		)


def retry_webhook_delivery(log_name: str):
	log = frappe.get_doc("Webhook Request Log", log_name)
	webhook = frappe.db.get_value(
		"Webhook",
		log.webhook,
		["request_method", "timeout", "max_retries", "enabled"],
		as_dict=True,
	)
	if not webhook or not webhook.enabled:
		log.db_set({"status": "Exhausted", "next_retry": None})
		return

	attempt = cint(log.attempt) + 1
	headers = json.loads(log.headers) if log.headers else {}
	data = json.loads(log.data) if log.data else {}
	res = None
	try:
		res = send_webhook_request(webhook.request_method, log.url, headers, data, webhook.timeout)
		res.raise_for_status()
		frappe.logger().debug({"webhook_success": res.text})
		log.db_set(
			{
				"status": "Delivered",
				"attempt": attempt,
				"next_retry": None,
				"response": res.text,
				"error": None,
			}
		)

	except Exception as e:
		frappe.logger().debug({"webhook_retry_error": e, "attempt": attempt})
		response = res.text if res is not None else None
		if attempt - 1 < cint(webhook.max_retries):
			log.db_set(
				{
					"status": "Failed",
					"attempt": attempt,
					"next_retry": get_next_retry(attempt),
					"response": response,
					"error": frappe.get_traceback(),
				}
			)
		else:
			log.db_set(
				{
					"status": "Exhausted",
					"attempt": attempt,
					"next_retry": None,
					"response": response,
					"error": frappe.get_traceback(),
				}
			)


def log_request(
	webhook: str,
	doctype: str,
	docname: str,
	url: str,
	headers: dict,
	data: dict,
	res: requests.Response | None = None,
	status: str | None = None,
	attempt: int = 1,
	next_retry=None,
):
	request_log = frappe.get_doc(
		{
			"doctype": "Webhook Request Log",
			"webhook": webhook,
			"reference_doctype": doctype,
			"reference_document": docname,
			"user": frappe.session.user if frappe.session.user else None,
			"url": url,
			"headers": frappe.as_json(headers) if headers else None,
			"data": frappe.as_json(data) if data else None,
			"response": res.text if res is not None else None,
			"error": frappe.get_traceback(),
			"status": status,
			"attempt": attempt,
			"next_retry": next_retry,
		}
	)

	request_log.save(ignore_permissions=True)


def get_webhook_headers(doc, webhook, data=None):
	headers = {}

	if webhook.enable_security:
		if data is None:
			data = get_webhook_data(doc, webhook)
		signature = base64.b64encode(
			hmac.new(
				webhook.get_password("webhook_secret").encode("utf8"),
				frappe.as_json(data).encode("utf8"),
				hashlib.sha256,
			).digest()
		).decode()
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


@frappe.whitelist()
def get_all_queues():
	"""Fetches all workers and returns a list of available queue names."""
	frappe.only_for("System Manager")

	return get_queues_timeout().keys()
