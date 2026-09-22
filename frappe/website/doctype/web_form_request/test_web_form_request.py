# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.website.doctype.web_form_request.web_form_request import (
	InvalidFieldsInValuesError,
	get_web_form_request,
	get_web_form_request_query,
)

test_dependencies = ["Web Form"]


class TestWebFormRequest(FrappeTestCase):
	def test_web_form_values_must_match_web_form_fields(self):
		with self.assertRaises(InvalidFieldsInValuesError) as ctx:
			self.create_web_form_request(web_form_values={"invalid_web_form_field": "value"})
		self.assertEqual(ctx.exception.invalid_fields, ("invalid_web_form_field",))

	def test_doc_values_must_match_reference_doctype_fields(self):
		with self.assertRaises(InvalidFieldsInValuesError) as ctx:
			self.create_web_form_request(doc_values={"invalid_doc_field": "value"})
		self.assertEqual(ctx.exception.invalid_fields, ("invalid_doc_field",))

	def test_get_web_form_request_query(self):
		frappe.local.form_dict = frappe._dict()
		self.assertEqual(get_web_form_request_query(), "")
		self.assertEqual(
			get_web_form_request_query("abc/def"),
			"?web_form_request_key=abc%2Fdef",
		)
		frappe.local.form_dict = frappe._dict(web_form_request_key="from-form-dict")
		self.assertEqual(get_web_form_request_query(), "?web_form_request_key=from-form-dict")

	def test_get_web_form_request_rejects_non_string_key(self):
		web_form_request = self.create_web_form_request()

		with self.assertRaises(frappe.PermissionError):
			get_web_form_request("manage-events", ["!=", ""])

		self.assertEqual(
			get_web_form_request("manage-events", web_form_request.key).name,
			web_form_request.name,
		)

	def create_web_form_request(self, web_form_values=None, doc_values=None):
		return frappe.get_doc(
			{
				"doctype": "Web Form Request",
				"web_form": "manage-events",
				"web_form_values": json.dumps(web_form_values or {}),
				"doc_values": json.dumps(doc_values or {}),
			}
		).insert(ignore_permissions=True)
