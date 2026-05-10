# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, set_request
from frappe.website.doctype.web_form.web_form import accept, delete
from frappe.website.serve import get_response_content

EXTRA_TEST_RECORD_DEPENDENCIES = ["Web Form"]


class TestWebForm(IntegrationTestCase):
	def setUp(self):
		frappe.conf.disable_website_cache = True

	def tearDown(self):
		frappe.conf.disable_website_cache = False
		frappe.set_user("Administrator")

	def test_accept(self):
		frappe.set_user("Administrator")

		doc = {
			"doctype": "Event",
			"subject": "_Test Event Web Form",
			"description": "_Test Event Description",
			"starts_on": "2014-09-09",
		}

		accept(web_form="manage-events", data=json.dumps(doc))

		self.event_name = frappe.db.get_value("Event", {"subject": "_Test Event Web Form"})
		self.assertTrue(self.event_name)

	def test_edit(self):
		self.test_accept()

		doc = {
			"doctype": "Event",
			"subject": "_Test Event Web Form",
			"description": "_Test Event Description 1",
			"starts_on": "2014-09-09",
			"name": self.event_name,
		}

		self.assertNotEqual(
			frappe.db.get_value("Event", self.event_name, "description"), doc.get("description")
		)

		accept("manage-events", json.dumps(doc))

		self.assertEqual(frappe.db.get_value("Event", self.event_name, "description"), doc.get("description"))

	def test_webform_render(self):
		set_request(method="GET", path="manage-events/new")
		content = get_response_content("manage-events/new")
		self.assertIn('<h1 class="ellipsis">New Manage Events</h1>', content)
		self.assertIn('data-doctype="Web Form"', content)
		self.assertIn('data-path="manage-events/new"', content)
		self.assertIn('source-type="Generator"', content)

	def test_webform_html_meta_is_added(self):
		set_request(method="GET", path="manage-events/new")
		content = self.normalize_html(get_response_content("manage-events/new"))

		self.assertIn(self.normalize_html('<meta name="title" content="Test Meta Form Title">'), content)
		self.assertIn(
			self.normalize_html('<meta property="og:title" content="Test Meta Form Title">'), content
		)
		self.assertIn(
			self.normalize_html('<meta property="og:description" content="Test Meta Form Description">'),
			content,
		)
		self.assertIn(
			self.normalize_html('<meta property="og:image" content="https://frappe.io/files/frappe.png">'),
			content,
		)

	def test_web_form_request_renders_prefilled_values_for_guest(self):
		web_form_request = self.create_web_form_request(
			web_form_values={
				"subject": "_Test Request Prefill",
				"starts_on": "2026-05-10",
			},
			doc_values={"description": "_Test Hidden Request Value"},
		)

		frappe.set_user("Guest")
		frappe.local.form_dict = frappe._dict(web_form_request_key=web_form_request.key)
		set_request(
			method="GET",
			path="manage-events/new",
			query_string=f"web_form_request_key={web_form_request.key}",
		)
		content = get_response_content("manage-events/new")

		self.assertIn("_Test Request Prefill", content)
		self.assertIn(web_form_request.key, content)
		self.assertNotIn("_Test Hidden Request Value", content)

	def test_web_form_request_allows_guest_submission_once(self):
		self.set_web_form_settings(key_required=1, login_required=0, allow_edit=0, allow_multiple=0)
		web_form_request = self.create_web_form_request(
			doc_values={
				"event_type": "Public",
				"event_category": "Meeting",
			}
		)

		frappe.set_user("Guest")
		doc = {
			"doctype": "Event",
			"subject": "_Test Request Submission",
			"description": "_Test Visible Description",
			"starts_on": "2026-05-10",
		}

		event = accept(
			web_form="manage-events",
			data=json.dumps(doc),
			web_form_request_key=web_form_request.key,
		)

		self.assertEqual(event.event_type, "Public")
		self.assertEqual(event.event_category, "Meeting")
		self.assertEqual(event.description, "_Test Visible Description")

		web_form_request.reload()
		self.assertTrue(web_form_request.used_on)
		self.assertEqual(web_form_request.reference_docname, event.name)

		with self.assertRaises(frappe.exceptions.LinkExpired):
			accept(
				web_form="manage-events",
				data=json.dumps(
					{
						"doctype": "Event",
						"subject": "_Test Request Submission Again",
						"starts_on": "2026-05-10",
					}
				),
				web_form_request_key=web_form_request.key,
			)

	def test_key_required_rejects_submission_without_key(self):
		self.set_web_form_settings(key_required=1, login_required=0)

		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			accept(
				web_form="manage-events",
				data=json.dumps(
					{
						"doctype": "Event",
						"subject": "_Test Request Missing Key",
						"starts_on": "2026-05-10",
					}
				),
			)

	def test_login_required_needs_key_and_login(self):
		self.set_web_form_settings(key_required=1, login_required=1)
		web_form_request = self.create_web_form_request(doc_values={"event_type": "Public"})
		doc = {
			"doctype": "Event",
			"subject": "_Test Request With Login",
			"starts_on": "2026-05-10",
		}

		frappe.set_user("Guest")
		with self.assertRaises(frappe.ValidationError):
			accept(
				web_form="manage-events",
				data=json.dumps(doc),
				web_form_request_key=web_form_request.key,
			)

		frappe.set_user("Administrator")
		with self.assertRaises(frappe.PermissionError):
			accept(web_form="manage-events", data=json.dumps(doc))

		event = accept(
			web_form="manage-events",
			data=json.dumps(doc),
			web_form_request_key=web_form_request.key,
		)
		self.assertEqual(event.event_type, "Public")

	def test_web_form_request_can_edit_existing_response(self):
		self.set_web_form_settings(key_required=1, login_required=0, allow_edit=1, allow_multiple=0)
		web_form_request = self.create_web_form_request(doc_values={"event_type": "Public"})

		frappe.set_user("Guest")
		event = accept(
			web_form="manage-events",
			data=json.dumps(
				{
					"doctype": "Event",
					"subject": "_Test Request Editable",
					"description": "_Test Before Edit",
					"starts_on": "2026-05-10",
				}
			),
			web_form_request_key=web_form_request.key,
		)

		event = accept(
			web_form="manage-events",
			data=json.dumps(
				{
					"doctype": "Event",
					"name": event.name,
					"subject": "_Test Request Editable",
					"description": "_Test After Edit",
					"starts_on": "2026-05-10",
				}
			),
			web_form_request_key=web_form_request.key,
		)

		self.assertEqual(event.description, "_Test After Edit")

	def test_web_form_request_can_submit_multiple_responses(self):
		self.set_web_form_settings(key_required=1, login_required=0, allow_multiple=1)
		web_form_request = self.create_web_form_request(doc_values={"event_type": "Public"})

		frappe.set_user("Guest")
		first_event = accept(
			web_form="manage-events",
			data=json.dumps(
				{
					"doctype": "Event",
					"subject": "_Test Request Multiple 1",
					"starts_on": "2026-05-10",
				}
			),
			web_form_request_key=web_form_request.key,
		)
		second_event = accept(
			web_form="manage-events",
			data=json.dumps(
				{
					"doctype": "Event",
					"subject": "_Test Request Multiple 2",
					"starts_on": "2026-05-10",
				}
			),
			web_form_request_key=web_form_request.key,
		)

		web_form_request.reload()
		self.assertNotEqual(first_event.name, second_event.name)
		self.assertFalse(web_form_request.used_on)

	def test_web_form_request_can_delete_existing_response(self):
		self.set_web_form_settings(
			key_required=1,
			login_required=0,
			allow_edit=1,
			allow_multiple=0,
			allow_delete=1,
		)
		web_form_request = self.create_web_form_request(doc_values={"event_type": "Public"})

		frappe.set_user("Guest")
		event = accept(
			web_form="manage-events",
			data=json.dumps(
				{
					"doctype": "Event",
					"subject": "_Test Request Delete",
					"starts_on": "2026-05-10",
				}
			),
			web_form_request_key=web_form_request.key,
		)

		delete("manage-events", event.name, web_form_request_key=web_form_request.key)
		self.assertFalse(frappe.db.exists("Event", event.name))

	def test_web_form_request_expiry_is_enforced(self):
		web_form_request = self.create_web_form_request(
			expires_on=add_to_date(None, minutes=-1),
			doc_values={"event_type": "Public"},
		)

		frappe.set_user("Guest")
		with self.assertRaises(frappe.exceptions.LinkExpired):
			accept(
				web_form="manage-events",
				data=json.dumps(
					{
						"doctype": "Event",
						"subject": "_Test Expired Request",
						"starts_on": "2026-05-10",
					}
				),
				web_form_request_key=web_form_request.key,
			)

	def test_guest_still_requires_login_without_web_form_request(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.ValidationError):
			accept(
				web_form="manage-events",
				data=json.dumps(
					{
						"doctype": "Event",
						"subject": "_Test Guest Without Request",
						"starts_on": "2026-05-10",
					}
				),
			)

	def create_web_form_request(
		self, web_form_values=None, doc_values=None, expires_on=None, reference_docname=None
	):
		return frappe.get_doc(
			{
				"doctype": "Web Form Request",
				"web_form": "manage-events",
				"reference_docname": reference_docname,
				"expires_on": expires_on,
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
