# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import unittest

import frappe
from frappe.integrations.doctype.webhook.webhook import get_webhook_headers, get_webhook_data


class TestWebhook(unittest.TestCase):
	def test_validate_doc_events(self):
		"Test creating a submit-related webhook for a non-submittable DocType"

		doc = frappe.new_doc("Webhook")
		doc.webhook_doctype = "User"
		doc.webhook_docevent = "on_submit"
		doc.request_url = "https://httpbin.org/post"
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_validate_request_url(self):
		"Test validation for the webhook request URL"

		doc = frappe.new_doc("Webhook")
		doc.webhook_doctype = "User"
		doc.webhook_docevent = "after_insert"
		doc.request_url = "httpbin.org?post"
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_validate_headers(self):
		"Test validation for request headers"

		doc = frappe.new_doc("Webhook")
		doc.webhook_doctype = "User"
		doc.webhook_docevent = "after_insert"
		doc.request_url = "https://httpbin.org/post"

		# test incomplete headers
		doc.webhook_headers = [{
			"key": "Content-Type"
		}]
		doc.save()
		headers = get_webhook_headers(doc=None, webhook=doc)
		self.assertEqual(headers, None)

		# test complete headers
		doc.webhook_headers = [{
			"key": "Content-Type",
			"value": "application/json"
		}]
		doc.save()
		headers = get_webhook_headers(doc=None, webhook=doc)
		self.assertEqual(headers, {"Content-Type": "application/json"})

	def test_validate_request_body_form(self):
		"Test validation of Form URL-Encoded request body"

		doc = frappe.new_doc("Webhook")
		doc.webhook_doctype = "User"
		doc.webhook_docevent = "after_insert"
		doc.request_url = "https://httpbin.org/post"
		doc.request_structure = "Form URL-Encoded"
		doc.set("webhook_data", [{
			"fieldname": "name",
			"key": "name"
		}])
		doc.webhook_json = """{
			"name": "Test User"
		}"""
		doc.save()
		self.assertEqual(doc.webhook_json, None)

		user = frappe.new_doc("User")
		user.first_name = frappe.mock("name")
		user.email = frappe.mock("email")
		user.save()
		data = get_webhook_data(user, webhook=doc)
		self.assertEqual(data, {"name": user.name})

	def test_validate_request_body_json(self):
		"Test validation of JSON request body"

		doc = frappe.new_doc("Webhook")
		doc.webhook_doctype = "User"
		doc.webhook_docevent = "after_insert"
		doc.request_url = "https://httpbin.org/post"
		doc.request_structure = "JSON"
		doc.set("webhook_data", [{
			"fieldname": "name",
			"key": "name"
		}])
		doc.webhook_json = """{
			"name": "{{ doc.name }}"
		}"""
		doc.save()
		self.assertEqual(doc.webhook_data, [])

		user = frappe.new_doc("User")
		user.first_name = frappe.mock("name")
		user.email = frappe.mock("email")
		user.save()
		data = get_webhook_data(user, webhook=doc)
		self.assertEqual(data, {"name": user.name})
