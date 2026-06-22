# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request
from frappe.website.doctype.web_form.web_form import accept, get_published_web_forms
from frappe.website.serve import get_response_content

EXTRA_TEST_RECORD_DEPENDENCIES = ["Web Form"]


class TestWebForm(IntegrationTestCase):
	def setUp(self):
		frappe.conf.disable_website_cache = True
		# isolate request state: rendering a specific document leaves `name`/`is_read`
		# in form_dict, which would otherwise leak into sibling tests' /new requests
		frappe.set_user("Administrator")
		frappe.local.form_dict = frappe._dict()

	def tearDown(self):
		frappe.conf.disable_website_cache = False
		frappe.set_user("Administrator")
		frappe.local.form_dict = frappe._dict()
		# drop any web form created during a test from the cached published-forms list
		get_published_web_forms.clear_cache()

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

	def test_webform_print(self):
		# Use Note: a viewer doesn't get standard print permission on it, so the share
		# key is what lets them print. (Event grants "print" to the "All" role, so it
		# can't exercise the share-key path.)
		web_form = frappe.get_doc(
			{
				"doctype": "Web Form",
				"title": "Test Note Print",
				"route": "test-note-print",
				"doc_type": "Note",
				"module": "Website",
				"login_required": 1,
				"allow_multiple": 1,
				"allow_edit": 1,
				"show_list": 1,
				"allow_print": 1,
				"published": 1,
				"web_form_fields": [
					{"fieldname": "title", "fieldtype": "Data", "label": "Title", "reqd": 1}
				],
			}
		).insert(ignore_permissions=True)
		get_published_web_forms.clear_cache()

		user = "test-web-form-print@example.com"
		if not frappe.db.exists("User", user):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": user,
					"first_name": "Test Web Form Print",
					"user_type": "Website User",
					"send_welcome_email": 0,
				}
			).insert(ignore_permissions=True)

		# the user owns the submission (so the web form lets them view it) but has no
		# standard print permission on Note
		frappe.set_user(user)
		note = frappe.get_doc({"doctype": "Note", "title": "_Test Note Print"}).insert(
			ignore_permissions=True
		)
		self.assertFalse(frappe.has_permission("Note", "print", note.name))

		path = f"{web_form.route}/{note.name}"
		set_request(method="GET", path=path)
		content = get_response_content(path)

		# the print link must carry a document share key, otherwise /printview rejects
		# the user and the print button errors out. See #19160.
		self.assertIn(f"/printview?doctype=Note&name={note.name}", content)
		self.assertIn("&key=", content)

		def share_key_count():
			return frappe.db.count(
				"Document Share Key", {"reference_doctype": "Note", "reference_docname": note.name}
			)

		self.assertEqual(share_key_count(), 1)

		# viewing again must reuse the key, not insert a new one on every request/day
		set_request(method="GET", path=path)
		get_response_content(path)
		self.assertEqual(share_key_count(), 1)

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
