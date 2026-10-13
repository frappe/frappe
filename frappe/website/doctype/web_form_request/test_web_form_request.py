# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import json

import frappe
from frappe.tests import IntegrationTestCase
from frappe.website.doctype.web_form_request.web_form_request import (
	InvalidFieldsInValuesError,
	get_web_form_request,
	get_web_form_request_query,
)

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = ["Web Form"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class TestWebFormRequest(IntegrationTestCase):
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

	def test_single_response_web_form_allows_only_one_reference(self):
		self.set_allow_multiple(0)
		web_form_request = self.create_web_form_request(references=[self.create_event()])

		web_form_request.append("references", self.reference_row(self.create_event()))
		with self.assertRaisesRegex(frappe.ValidationError, "only one reference"):
			web_form_request.save(ignore_permissions=True)

	def test_multiple_response_web_form_allows_many_references(self):
		self.set_allow_multiple(1)
		web_form_request = self.create_web_form_request(
			references=[self.create_event(), self.create_event()]
		)

		self.assertEqual(len(web_form_request.references), 2)

	def test_references_added_before_single_response_stay_valid(self):
		self.set_allow_multiple(1)
		web_form_request = self.create_web_form_request(
			references=[self.create_event(), self.create_event()]
		)

		self.set_allow_multiple(0)
		web_form_request.reload()
		web_form_request.save(ignore_permissions=True)

		web_form_request.append("references", self.reference_row(self.create_event()))
		with self.assertRaisesRegex(frappe.ValidationError, "only one reference"):
			web_form_request.save(ignore_permissions=True)

	def set_allow_multiple(self, allow_multiple):
		current = frappe.db.get_value("Web Form", "manage-events", "allow_multiple")

		def restore():
			frappe.db.set_value(
				"Web Form", "manage-events", "allow_multiple", current, update_modified=False
			)
			frappe.clear_document_cache("Web Form", "manage-events")

		self.addCleanup(restore)
		frappe.db.set_value(
			"Web Form", "manage-events", "allow_multiple", allow_multiple, update_modified=False
		)
		frappe.clear_document_cache("Web Form", "manage-events")

	def create_event(self):
		event = frappe.get_doc(
			{"doctype": "Event", "subject": "_Test Web Form Request Reference", "starts_on": "2014-09-09"}
		).insert(ignore_permissions=True)
		return event.name

	def reference_row(self, link_name):
		return {"link_doctype": "Event", "link_name": link_name}

	def create_web_form_request(self, web_form_values=None, doc_values=None, references=None):
		return frappe.get_doc(
			{
				"doctype": "Web Form Request",
				"web_form": "manage-events",
				"references": [self.reference_row(name) for name in references or []],
				"web_form_values": json.dumps(web_form_values or {}),
				"doc_values": json.dumps(doc_values or {}),
			}
		).insert(ignore_permissions=True)
