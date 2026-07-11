# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import json
from contextlib import contextmanager
from unittest.mock import patch

import responses
from responses.matchers import json_params_matcher

import frappe
from frappe.integrations.doctype.webhook import flush_webhook_execution_queue
from frappe.integrations.doctype.webhook.webhook import (
	WEBHOOK_SECRET_HEADER,
	enqueue_webhook,
	get_webhook_data,
	get_webhook_headers,
	retry_failed_webhooks,
)
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import timeout
from frappe.utils import add_to_date, now_datetime


@contextmanager
def get_test_webhook(config):
	wh = frappe.get_doc(config)
	if not wh.name:
		wh.name = frappe.generate_hash()
	wh.insert()
	wh.reload()
	try:
		yield wh
	finally:
		wh.delete()


class TestWebhook(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		# delete any existing webhooks
		frappe.db.delete("Webhook")
		# Delete existing logs if any
		frappe.db.delete("Webhook Request Log")
		super().setUpClass()
		# create test webhooks
		cls.create_sample_webhooks()

	@classmethod
	def create_sample_webhooks(cls):
		samples_webhooks_data = [
			{
				"name": frappe.generate_hash(),
				"webhook_doctype": "User",
				"webhook_docevent": "after_insert",
				"request_url": "https://httpbin.org/post",
				"condition": "doc.email",
				"enabled": True,
			},
			{
				"name": frappe.generate_hash(),
				"webhook_doctype": "User",
				"webhook_docevent": "after_insert",
				"request_url": "https://httpbin.org/post",
				"condition": "doc.first_name",
				"enabled": False,
			},
		]

		cls.sample_webhooks = []
		for wh_fields in samples_webhooks_data:
			wh = frappe.new_doc("Webhook")
			wh.update(wh_fields)
			wh.insert()
			cls.sample_webhooks.append(wh)

	@classmethod
	def tearDownClass(cls):
		# delete any existing webhooks
		frappe.db.rollback()
		frappe.db.delete("Webhook")
		frappe.db.commit()

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def setUp(self):
		# retrieve or create a User webhook for `after_insert`
		self.responses = responses.RequestsMock()
		self.responses.start()

		self.responses.add(
			responses.POST,
			"https://httpbin.org/post",
			status=200,
			json={},
		)

		webhook_fields = {
			"webhook_doctype": "User",
			"webhook_docevent": "after_insert",
			"request_url": "https://httpbin.org/post",
		}

		if frappe.db.exists("Webhook", webhook_fields):
			self.webhook = frappe.get_doc("Webhook", webhook_fields)
		else:
			self.webhook = frappe.new_doc("Webhook")
			self.webhook.update(webhook_fields)

		# create a User document
		self.user = frappe.new_doc("User")
		self.user.first_name = frappe.mock("name")
		self.user.email = frappe.mock("email")
		self.user.save()

		# Create another test user specific to this test
		self.test_user = frappe.new_doc("User")
		self.test_user.email = "user1@integration.webhooks.test.com"
		self.test_user.first_name = "user1"
		self.test_user.send_welcome_email = False
		frappe.db.commit()

	def tearDown(self) -> None:
		self.user.delete()
		self.test_user.delete()

		self.responses.stop()
		self.responses.reset()
		super().tearDown()

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_webhook_trigger_with_enabled_webhooks(self):
		"""Test webhook trigger for enabled webhooks"""

		frappe.client_cache.delete_value("webhooks")

		# Insert the user to db
		self.test_user.insert()

		webhooks = frappe.client_cache.get_value("webhooks")
		self.assertTrue("User" in webhooks)
		self.assertEqual(len(webhooks.get("User")), 1)

		# only 1 hook (enabled) must be queued
		self.assertEqual(len(frappe.local._webhook_queue), 1)
		execution = frappe.local._webhook_queue[0]
		self.assertEqual(execution.webhook.name, self.sample_webhooks[0].name)
		self.assertEqual(execution.doc.name, self.test_user.name)

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_validate_doc_events(self):
		"Test creating a submit-related webhook for a non-submittable DocType"

		self.webhook.webhook_docevent = "on_submit"
		self.assertRaises(frappe.ValidationError, self.webhook.save)

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_validate_request_url(self):
		"Test validation for the webhook request URL"

		self.webhook.request_url = "httpbin.org?post"
		self.assertRaises(frappe.ValidationError, self.webhook.save)

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_validate_headers(self):
		"Test validation for request headers"

		# test incomplete headers
		self.webhook.set("webhook_headers", [{"key": "Content-Type"}])
		self.webhook.save()
		headers = get_webhook_headers(doc=None, webhook=self.webhook)
		self.assertEqual(headers, {})

		# test complete headers
		self.webhook.set("webhook_headers", [{"key": "Content-Type", "value": "application/json"}])
		self.webhook.save()
		headers = get_webhook_headers(doc=None, webhook=self.webhook)
		self.assertEqual(headers, {"Content-Type": "application/json"})

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_validate_request_body_form(self):
		"Test validation of Form URL-Encoded request body"

		self.webhook.request_structure = "Form URL-Encoded"
		self.webhook.set("webhook_data", [{"fieldname": "name", "key": "name"}])
		self.webhook.webhook_json = """{
			"name": "{{ doc.name }}"
		}"""
		self.webhook.save()
		self.assertEqual(self.webhook.webhook_json, None)

		data = get_webhook_data(doc=self.user, webhook=self.webhook)
		self.assertEqual(data, {"name": self.user.name})

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_validate_request_body_json(self):
		"Test validation of JSON request body"

		self.webhook.request_structure = "JSON"
		self.webhook.set("webhook_data", [{"fieldname": "name", "key": "name"}])
		self.webhook.webhook_json = """{
			"name": "{{ doc.name }}"
		}"""
		self.webhook.save()
		self.assertEqual(self.webhook.webhook_data, [])

		data = get_webhook_data(doc=self.user, webhook=self.webhook)
		self.assertEqual(data, {"name": self.user.name})

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_webhook_req_log_creation(self):
		self.responses.add(
			responses.POST,
			"https://httpbin.org/post",
			status=200,
			json={},
		)

		if not frappe.db.get_value("User", "user2@integration.webhooks.test.com"):
			user = frappe.get_doc(
				{"doctype": "User", "email": "user2@integration.webhooks.test.com", "first_name": "user2"}
			).insert()
		else:
			user = frappe.get_doc("User", "user2@integration.webhooks.test.com")

		webhook = frappe.get_doc("Webhook", {"webhook_doctype": "User"})
		enqueue_webhook(user, webhook)

		self.assertTrue(frappe.get_all("Webhook Request Log", pluck="name"))

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_webhook_with_array_body(self):
		"""Check if array request body are supported."""
		wh_config = {
			"doctype": "Webhook",
			"webhook_doctype": "Note",
			"webhook_docevent": "on_change",
			"enabled": 1,
			"request_url": "https://httpbin.org/post",
			"request_method": "POST",
			"request_structure": "JSON",
			"webhook_json": '[\r\n{% for n in range(3) %}\r\n    {\r\n        "title": "{{ doc.title }}"    }\r\n    {%- if not loop.last -%}\r\n        , \r\n    {%endif%}\r\n{%endfor%}\r\n]',
			"meets_condition": "Yes",
			"webhook_headers": [
				{
					"key": "Content-Type",
					"value": "application/json",
				}
			],
		}

		doc = frappe.new_doc("Note")
		doc.title = "Test Webhook Note"
		final_title = frappe.generate_hash()

		expected_req = [{"title": final_title} for _ in range(3)]
		self.responses.add(
			responses.POST,
			"https://httpbin.org/post",
			status=200,
			json=expected_req,
			match=[json_params_matcher(expected_req)],
		)

		with get_test_webhook(wh_config):
			# It should only execute once in a transaction
			doc.insert()
			doc.reload()
			doc.save()
			doc = frappe.get_doc(doc.doctype, doc.name)
			doc.title = final_title
			doc.save()
			flush_webhook_execution_queue()
			log = frappe.get_last_doc("Webhook Request Log")
			self.assertEqual(len(json.loads(log.response)), 3)

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_webhook_with_dynamic_url_enabled(self):
		wh_config = {
			"doctype": "Webhook",
			"webhook_doctype": "Note",
			"webhook_docevent": "after_insert",
			"enabled": 1,
			"request_url": "https://httpbin.org/anything/{{ doc.doctype }}",
			"is_dynamic_url": 1,
			"request_method": "POST",
			"request_structure": "JSON",
			"webhook_json": "{}",
			"meets_condition": "Yes",
			"webhook_headers": [
				{
					"key": "Content-Type",
					"value": "application/json",
				}
			],
		}

		self.responses.add(
			responses.POST,
			"https://httpbin.org/anything/Note",
			status=200,
		)

		with get_test_webhook(wh_config) as wh:
			doc = frappe.new_doc("Note")
			doc.title = "Test Webhook Note"
			enqueue_webhook(doc, wh)

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_webhook_with_dynamic_url_disabled(self):
		wh_config = {
			"doctype": "Webhook",
			"webhook_doctype": "Note",
			"webhook_docevent": "after_insert",
			"enabled": 1,
			"request_url": "https://httpbin.org/anything/{{doc.doctype}}",
			"is_dynamic_url": 0,
			"request_method": "POST",
			"request_structure": "JSON",
			"webhook_json": "{}",
			"meets_condition": "Yes",
			"webhook_headers": [
				{
					"key": "Content-Type",
					"value": "application/json",
				}
			],
		}

		self.responses.add(
			responses.POST,
			"https://httpbin.org/anything/{{doc.doctype}}",
			status=200,
		)

		with get_test_webhook(wh_config) as wh:
			doc = frappe.new_doc("Note")
			doc.title = "Test Webhook Note"
			enqueue_webhook(doc, wh)

	def retry_webhook_config(self, url, max_retries=3, webhook_docevent="after_insert"):
		return {
			"doctype": "Webhook",
			"webhook_doctype": "Note",
			"webhook_docevent": webhook_docevent,
			"enabled": 1,
			"request_url": url,
			"request_method": "POST",
			"request_structure": "JSON",
			"webhook_json": "{}",
			"max_retries": max_retries,
		}

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_webhook_failure_schedules_retry(self):
		"""A failed delivery logs a single row awaiting a scheduled retry"""
		url = "https://httpbin.org/retry-schedule"
		self.responses.add(responses.POST, url, status=500)

		with get_test_webhook(self.retry_webhook_config(url, max_retries=3)) as wh:
			doc = frappe.new_doc("Note")
			doc.title = "Retry Note"
			enqueue_webhook(doc, wh)

			log = frappe.get_last_doc("Webhook Request Log", filters={"webhook": wh.name})
			self.assertEqual(log.status, "Failed")
			self.assertEqual(log.attempt, 1)
			self.assertIsNotNone(log.next_retry)

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_webhook_without_retries_is_exhausted(self):
		"""With max_retries set to 0, a failed delivery is not retried"""
		url = "https://httpbin.org/exhaust-now"
		self.responses.add(responses.POST, url, status=500)

		with get_test_webhook(self.retry_webhook_config(url, max_retries=0)) as wh:
			doc = frappe.new_doc("Note")
			doc.title = "No Retry Note"
			enqueue_webhook(doc, wh)

			log = frappe.get_last_doc("Webhook Request Log", filters={"webhook": wh.name})
			self.assertEqual(log.status, "Exhausted")
			self.assertIsNone(log.next_retry)

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_sweeper_redelivers_due_webhook(self):
		"""The sweeper re-sends a due delivery and marks it delivered on success"""
		url = "https://httpbin.org/sweeper-success"
		self.responses.add(responses.POST, url, status=500)
		self.responses.add(responses.POST, url, status=200, json={})

		with get_test_webhook(self.retry_webhook_config(url, max_retries=3)) as wh:
			doc = frappe.new_doc("Note")
			doc.title = "Sweeper Note"
			enqueue_webhook(doc, wh)

			log = frappe.get_last_doc("Webhook Request Log", filters={"webhook": wh.name})
			self.assertEqual(log.status, "Failed")

			frappe.db.set_value(
				"Webhook Request Log", log.name, "next_retry", add_to_date(now_datetime(), seconds=-1)
			)
			retry_failed_webhooks()

			log.reload()
			self.assertEqual(log.status, "Delivered")
			self.assertEqual(log.attempt, 2)
			self.assertIsNone(log.next_retry)

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_sweeper_exhausts_after_max_retries(self):
		"""The sweeper stops retrying once max_retries is reached"""
		url = "https://httpbin.org/sweeper-exhaust"
		self.responses.add(responses.POST, url, status=500)

		with get_test_webhook(self.retry_webhook_config(url, max_retries=1)) as wh:
			doc = frappe.new_doc("Note")
			doc.title = "Exhaust Note"
			enqueue_webhook(doc, wh)

			log = frappe.get_last_doc("Webhook Request Log", filters={"webhook": wh.name})
			self.assertEqual(log.status, "Failed")

			frappe.db.set_value(
				"Webhook Request Log", log.name, "next_retry", add_to_date(now_datetime(), seconds=-1)
			)
			retry_failed_webhooks()

			log.reload()
			self.assertEqual(log.status, "Exhausted")
			self.assertEqual(log.attempt, 2)
			self.assertIsNone(log.next_retry)

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_workflow_transition_failure_raises_without_scheduling(self):
		"""A failed workflow_transition webhook raises instead of scheduling a retry"""
		url = "https://httpbin.org/workflow-fail"
		self.responses.add(responses.POST, url, status=500)

		config = self.retry_webhook_config(url, max_retries=3, webhook_docevent="workflow_transition")
		with get_test_webhook(config) as wh:
			doc = frappe.new_doc("Note")
			doc.title = "Workflow Note"
			with self.assertRaises(Exception):
				enqueue_webhook(doc, wh)

			log = frappe.get_last_doc("Webhook Request Log", filters={"webhook": wh.name})
			self.assertEqual(log.status, "Exhausted")
			self.assertIsNone(log.next_retry)

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_sweeper_reschedules_when_retries_remain(self):
		"""A retry that fails with attempts left stays Failed and is scheduled again"""
		url = "https://httpbin.org/sweeper-reschedule"
		self.responses.add(responses.POST, url, status=500)
		self.responses.add(responses.POST, url, status=500)

		with get_test_webhook(self.retry_webhook_config(url, max_retries=2)) as wh:
			doc = frappe.new_doc("Note")
			doc.title = "Reschedule Note"
			enqueue_webhook(doc, wh)

			log = frappe.get_last_doc("Webhook Request Log", filters={"webhook": wh.name})
			frappe.db.set_value(
				"Webhook Request Log", log.name, "next_retry", add_to_date(now_datetime(), seconds=-1)
			)
			retry_failed_webhooks()

			log.reload()
			self.assertEqual(log.status, "Failed")
			self.assertEqual(log.attempt, 2)
			self.assertIsNotNone(log.next_retry)

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_sweeper_skips_delivery_already_in_flight(self):
		"""A due delivery whose retry job is still queued is not sent again"""
		url = "https://httpbin.org/sweeper-in-flight"
		self.responses.add(responses.POST, url, status=500)

		with get_test_webhook(self.retry_webhook_config(url, max_retries=3)) as wh:
			doc = frappe.new_doc("Note")
			doc.title = "In Flight Note"
			enqueue_webhook(doc, wh)

			log = frappe.get_last_doc("Webhook Request Log", filters={"webhook": wh.name})
			frappe.db.set_value(
				"Webhook Request Log", log.name, "next_retry", add_to_date(now_datetime(), seconds=-1)
			)

			with patch("frappe.integrations.doctype.webhook.webhook.is_job_enqueued", return_value=True):
				retry_failed_webhooks()

			log.reload()
			self.assertEqual(log.status, "Failed")
			self.assertEqual(log.attempt, 1)

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_retry_stops_when_webhook_disabled(self):
		"""A retry is exhausted without resending when the webhook is disabled"""
		url = "https://httpbin.org/sweeper-disabled"
		self.responses.add(responses.POST, url, status=500)

		with get_test_webhook(self.retry_webhook_config(url, max_retries=3)) as wh:
			doc = frappe.new_doc("Note")
			doc.title = "Disabled Note"
			enqueue_webhook(doc, wh)

			log = frappe.get_last_doc("Webhook Request Log", filters={"webhook": wh.name})
			frappe.db.set_value("Webhook", wh.name, "enabled", 0)
			frappe.db.set_value(
				"Webhook Request Log", log.name, "next_retry", add_to_date(now_datetime(), seconds=-1)
			)
			retry_failed_webhooks()

			log.reload()
			self.assertEqual(log.status, "Exhausted")
			self.assertIsNone(log.next_retry)

	def test_secured_webhook_signs_payload_with_string_header(self):
		"""A secured webhook stores its signature as a string so it survives serialization and replay"""
		config = self.retry_webhook_config("https://httpbin.org/secured")
		config["enable_security"] = 1
		config["webhook_secret"] = "super-secret"

		with get_test_webhook(config) as wh:
			doc = frappe.new_doc("Note")
			doc.title = "Secured Note"
			headers = get_webhook_headers(doc, wh, data=get_webhook_data(doc, wh))

			self.assertIn(WEBHOOK_SECRET_HEADER, headers)
			self.assertIsInstance(headers[WEBHOOK_SECRET_HEADER], str)

	@timeout(5, "Test webhooks should never wait, check mocked responses.")
	def test_unbuildable_request_is_exhausted(self):
		"""A webhook whose dynamic URL fails to render is exhausted without a retry"""
		config = self.retry_webhook_config("http://example.com/{{ doc.missing.attr }}")
		config["is_dynamic_url"] = 1

		with get_test_webhook(config) as wh:
			doc = frappe.new_doc("Note")
			doc.title = "Unbuildable Note"
			enqueue_webhook(doc, wh)

			log = frappe.get_last_doc("Webhook Request Log", filters={"webhook": wh.name})
			self.assertEqual(log.status, "Exhausted")
			self.assertIsNone(log.next_retry)
