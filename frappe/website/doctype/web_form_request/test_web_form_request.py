# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import json

import frappe
from frappe.tests import IntegrationTestCase
from frappe.website.doctype.web_form_request.web_form_request import (
	IllegalReferenceDocnameForMultipleResponsesError,
	InvalidFieldsInValuesError,
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

	def test_reference_docname_cannot_be_set_for_multiple_responses(self):
		self.set_web_form_settings(allow_multiple=1)
		event = frappe.get_doc(
			{
				"doctype": "Event",
				"subject": "_Test Web Form Request Reference",
				"starts_on": "2026-05-10",
				"event_type": "Private",
			}
		).insert(ignore_permissions=True)

		with self.assertRaises(IllegalReferenceDocnameForMultipleResponsesError):
			self.create_web_form_request(reference_docname=event.name)

	def create_web_form_request(self, web_form_values=None, doc_values=None, reference_docname=None):
		return frappe.get_doc(
			{
				"doctype": "Web Form Request",
				"web_form": "manage-events",
				"reference_docname": reference_docname,
				"web_form_values": json.dumps(web_form_values or {}),
				"doc_values": json.dumps(doc_values or {}),
			}
		).insert(ignore_permissions=True)

	def set_web_form_settings(self, **settings):
		current_settings = frappe.db.get_value("Web Form", "manage-events", list(settings), as_dict=True)

		def restore_settings():
			frappe.db.set_value("Web Form", "manage-events", current_settings, update_modified=False)
			frappe.clear_document_cache("Web Form", "manage-events")

		self.addCleanup(restore_settings)
		frappe.db.set_value("Web Form", "manage-events", settings, update_modified=False)
		frappe.clear_document_cache("Web Form", "manage-events")
