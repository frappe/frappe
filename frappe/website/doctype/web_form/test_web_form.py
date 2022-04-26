# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals

import json
import unittest

import frappe
from frappe.website.doctype.web_form.web_form import accept
from frappe.website.render import build_page

test_dependencies = ["Web Form"]


class TestWebForm(unittest.TestCase):
	def setUp(self):
		frappe.conf.disable_website_cache = True
		frappe.local.path = None

	def tearDown(self):
		frappe.conf.disable_website_cache = False
		frappe.local.path = None
		frappe.local.request_ip = None
		frappe.form_dict.web_form = None
		frappe.form_dict.data = None
		frappe.form_dict.docname = None

	def test_accept(self):
		frappe.set_user("Administrator")

		doc = {
			"doctype": "Event",
			"subject": "_Test Event Web Form",
			"description": "_Test Event Description",
			"starts_on": "2014-09-09",
		}

		frappe.form_dict.web_form = "manage-events"
		frappe.form_dict.data = json.dumps(doc)
		frappe.local.request_ip = "127.0.0.1"

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

		self.assertNotEquals(
			frappe.db.get_value("Event", self.event_name, "description"), doc.get("description")
		)

		frappe.form_dict.web_form = "manage-events"
		frappe.form_dict.docname = self.event_name
		frappe.form_dict.data = json.dumps(doc)

		accept(web_form="manage-events", docname=self.event_name, data=json.dumps(doc))

		self.assertEqual(
			frappe.db.get_value("Event", self.event_name, "description"), doc.get("description")
		)
