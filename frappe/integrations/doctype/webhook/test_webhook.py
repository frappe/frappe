# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import json
import socket
from contextlib import contextmanager
<<<<<<< HEAD
=======
from io import BytesIO
from unittest.mock import patch
>>>>>>> a917cb3 (fix(webhook): use shared request session)

import responses
from responses.matchers import json_params_matcher
from urllib3.response import HTTPResponse

import frappe
from frappe.integrations.doctype.webhook import flush_webhook_execution_queue
from frappe.integrations.doctype.webhook.webhook import (
	enqueue_webhook,
	get_webhook_data,
	get_webhook_headers,
<<<<<<< HEAD
)
from frappe.tests.utils import FrappeTestCase
=======
	retry_failed_webhooks,
	send_webhook_request,
)
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.tests.classes.context_managers import timeout
from frappe.utils import add_to_date, now_datetime
from frappe.utils.safe_exec import BlockedRequest


class TestWebhookRequest(UnitTestCase):
	def setUp(self):
		super().setUp()
		self.enterContext(self.set_user("webhook@example.com"))
		self.config = {}
		self.enterContext(patch("frappe.get_common_site_config", return_value=self.config))
		self.resolver = self.enterContext(patch("socket.getaddrinfo", side_effect=self.resolve_host))
		# Keep the real SSRF guard, but never send traffic over the network.
		self.transport = self.enterContext(patch("urllib3.connectionpool.HTTPConnectionPool._make_request"))
		self.transport.side_effect = lambda *args, **kwargs: self.response()

	@staticmethod
	def resolve_host(host, port, *args, **kwargs):
		address = "93.184.216.34" if host == "example.com" else host
		return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, port))]

	@staticmethod
	def response(status=200, headers=None):
		return HTTPResponse(
			body=BytesIO(b"webhook response"), status=status, headers=headers or {}, preload_content=False
		)

	def test_public_delivery(self):
		for scheme in ("http", "https"):
			with self.subTest(scheme=scheme):
				response = send_webhook_request("POST", f"{scheme}://example.com/", {}, {}, 5)
				self.assertEqual(response.status_code, 200)
				self.assertEqual(response.text, "webhook response")
		self.assertEqual(self.transport.call_count, 2)

	def test_internal_destinations_are_blocked(self):
		for url in (
			"http://169.254.169.254/latest/meta-data/",
			"http://127.0.0.1/",
			"http://10.0.0.1/",
			"http://172.16.0.1/",
			"http://192.168.0.1/",
			"http://[::1]/",
		):
			with self.subTest(url=url), self.assertRaises(BlockedRequest):
				send_webhook_request("POST", url, {}, {}, 5)
		self.transport.assert_not_called()

	def test_hostname_resolving_to_internal_address_is_blocked(self):
		self.resolver.side_effect = None
		self.resolver.return_value = self.resolve_host("10.0.0.1", 80)
		with self.assertRaises(BlockedRequest):
			send_webhook_request("POST", "http://example.com/", {}, {}, 5)
		self.transport.assert_not_called()

	def test_redirect_to_internal_destination_is_blocked(self):
		self.transport.side_effect = lambda *args, **kwargs: self.response(
			302, {"Location": "http://169.254.169.254/latest/meta-data/"}
		)
		with self.assertRaises(BlockedRequest):
			send_webhook_request("POST", "https://example.com/", {}, {}, 5)
		self.transport.assert_called_once()

	def test_internal_destination_can_be_allowed_by_operator(self):
		self.config["allow_internal_webhook_urls"] = True
		response = send_webhook_request("POST", "http://127.0.0.1/", {}, {}, 5)
		self.assertEqual(response.status_code, 200)
		self.transport.assert_called_once()
>>>>>>> a917cb3 (fix(webhook): use shared request session)

	def test_failed_delivery_is_not_retried_by_transport(self):
		self.transport.side_effect = lambda *args, **kwargs: self.response(500)
		for allow_internal in (False, True):
			self.config["allow_internal_webhook_urls"] = allow_internal
			for method in ("POST", "PUT", "DELETE"):
				with self.subTest(allow_internal=allow_internal, method=method):
					self.transport.reset_mock()
					response = send_webhook_request(method, "https://example.com/", {}, {}, 5)
					self.transport.assert_called_once()
					self.assertEqual(response.status_code, 500)
					self.assertEqual(response.text, "webhook response")


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


class TestWebhook(FrappeTestCase):
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

	def setUp(self):
		# retrieve or create a User webhook for `after_insert`
		self.responses = responses.RequestsMock()
		self.responses.start()
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

	def tearDown(self) -> None:
		self.user.delete()
		self.test_user.delete()

		self.responses.stop()
		self.responses.reset()
		super().tearDown()

	def test_webhook_trigger_with_enabled_webhooks(self):
		"""Test webhook trigger for enabled webhooks"""

		frappe.cache.delete_value("webhooks")

		# Insert the user to db
		self.test_user.insert()

		webhooks = frappe.cache.get_value("webhooks")
		self.assertTrue("User" in webhooks)
		self.assertEqual(len(webhooks.get("User")), 1)

		# only 1 hook (enabled) must be queued
		self.assertEqual(len(frappe.local._webhook_queue), 1)
		execution = frappe.local._webhook_queue[0]
		self.assertEqual(execution.webhook.name, self.sample_webhooks[0].name)
		self.assertEqual(execution.doc.name, self.test_user.name)

	def test_validate_doc_events(self):
		"Test creating a submit-related webhook for a non-submittable DocType"

		self.webhook.webhook_docevent = "on_submit"
		self.assertRaises(frappe.ValidationError, self.webhook.save)

	def test_validate_request_url(self):
		"Test validation for the webhook request URL"

		self.webhook.request_url = "httpbin.org?post"
		self.assertRaises(frappe.ValidationError, self.webhook.save)

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
