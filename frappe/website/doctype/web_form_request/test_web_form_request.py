# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import json

import frappe
from frappe.tests import IntegrationTestCase
from frappe.website.doctype.web_form.web_form import get_published_web_forms
from frappe.website.doctype.web_form_request.web_form_request import (
	InvalidFieldsInValuesError,
	create_for_document,
	get_request_forms_by_doctype,
	get_requests_for_document,
	get_web_form_request,
	get_web_form_request_query,
)

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = ["Web Form"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class TestWebFormRequest(IntegrationTestCase):
	def setUp(self):
		self.user = "test@example.com"
		user = frappe.get_doc("User", self.user)
		user.add_roles("Website Manager")
		self.addCleanup(user.remove_roles, "Website Manager")
		self.addCleanup(frappe.set_user, "Administrator")

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

	def test_create_for_document_binds_record_to_edit_link(self):
		self.set_web_form_settings(published=1, key_required=1, allow_edit=1)
		frappe.set_user(self.user)
		event = self.create_event()

		url = create_for_document("manage-events", event.name, expires_on="2099-01-01 00:00:00")

		request = frappe.get_last_doc("Web Form Request", {"web_form": "manage-events"})
		self.assertTrue(request.has_reference(event.name))
		self.assertEqual(request.references[0].link_doctype, "Event")
		self.assertTrue(url.endswith(f"/{event.name}/edit?web_form_request_key={request.key}"))

	def test_create_for_document_needs_a_key_required_editable_form(self):
		frappe.set_user(self.user)
		event = self.create_event()

		for settings in ({"key_required": 0, "allow_edit": 1}, {"key_required": 1, "allow_edit": 0}):
			self.set_web_form_settings(published=1, **settings)
			with self.assertRaises(frappe.ValidationError):
				create_for_document("manage-events", event.name)

	def test_create_for_document_needs_write_permission_on_record(self):
		self.set_web_form_settings(published=1, key_required=1, allow_edit=1)
		event = self.create_event(event_type="Private")
		participant_event = self.create_event(
			event_type="Private",
			event_participants=[
				{"reference_doctype": "User", "reference_docname": self.user, "email": self.user}
			],
		)

		frappe.set_user(self.user)
		self.assertTrue(frappe.has_permission("Event", "read", participant_event.name))
		for name in (event.name, participant_event.name):
			with self.assertRaises(frappe.PermissionError):
				create_for_document("manage-events", name)

	def test_request_forms_need_create_permission(self):
		self.set_web_form_settings(published=1, key_required=1, allow_edit=1)

		frappe.set_user(self.user)
		title = frappe.db.get_value("Web Form", "manage-events", "title")
		self.assertIn({"value": "manage-events", "label": title}, get_request_forms_by_doctype()["Event"])

		frappe.set_user("Guest")
		self.assertEqual(get_request_forms_by_doctype(), {})

	def test_requests_for_document_report_status(self):
		self.set_web_form_settings(published=1, key_required=1, allow_edit=1)
		frappe.set_user(self.user)
		event = self.create_event()
		create_for_document("manage-events", event.name, expires_on="2099-01-01 00:00:00")
		create_for_document("manage-events", event.name, expires_on="2000-01-01 00:00:00")

		requests = get_requests_for_document("Event", event.name)

		self.assertEqual(sorted(r.status for r in requests), ["Expired", "Not Used"])
		self.assertTrue(all("key" not in r for r in requests))
		not_used = next(r for r in requests if r.status == "Not Used")
		self.assertIn("web_form_request_key=", not_used.url)
		expired = next(r for r in requests if r.status == "Expired")
		self.assertIsNone(expired.get("url"))

	def set_web_form_settings(self, **settings):
		current = frappe.db.get_value("Web Form", "manage-events", list(settings), as_dict=True)

		def restore():
			frappe.db.set_value("Web Form", "manage-events", current, update_modified=False)
			get_published_web_forms.clear_cache()

		self.addCleanup(restore)
		frappe.db.set_value("Web Form", "manage-events", settings, update_modified=False)
		get_published_web_forms.clear_cache()

	def create_event(self, event_type="Public", event_participants=None):
		return frappe.get_doc(
			{
				"doctype": "Event",
				"subject": "_Test Web Form Request Event",
				"event_type": event_type,
				"starts_on": "2026-05-10 10:00:00",
				"event_participants": event_participants or [],
			}
		).insert()

	def create_web_form_request(self, web_form_values=None, doc_values=None):
		return frappe.get_doc(
			{
				"doctype": "Web Form Request",
				"web_form": "manage-events",
				"web_form_values": json.dumps(web_form_values or {}),
				"doc_values": json.dumps(doc_values or {}),
			}
		).insert(ignore_permissions=True)
