# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest, json

from frappe.website.render import build_page
from frappe.website.doctype.web_form.web_form import accept

test_records = frappe.get_test_records('Web Form')

class TestWebForm(unittest.TestCase):
	def setUp(self):
		frappe.conf.disable_website_cache = True
		frappe.local.path = None

	def tearDown(self):
		frappe.conf.disable_website_cache = False
		frappe.local.path = None

	def test_basic(self):
		frappe.set_user("Guest")
		html = build_page("manage-events")
		self.assertTrue('<div class="login-required">' in html)

	def test_logged_in(self):
		frappe.set_user("Administrator")
		html = build_page("manage-events")
		self.assertFalse('<div class="login-required">' in html)
		self.assertTrue('"/manage-events?new=1"' in html)

	def test_new(self):
		frappe.set_user("Administrator")
		frappe.local.form_dict.new = 1
		html = build_page("manage-events")
		self.assertTrue('name="subject"' in html)

	def test_accept(self):
		frappe.set_user("Administrator")
		accept(web_form='manage-events', data=json.dumps({
			'doctype': 'Event',
			'subject': '_Test Event Web Form',
			'description': '_Test Event Description',
			'starts_on': '2014-09-09'
		}))

		self.event_name = frappe.db.get_value("Event",
			{"subject": "_Test Event Web Form"})
		self.assertTrue(self.event_name)

	def test_edit(self):
		self.test_accept()
		doc={
			'doctype': 'Event',
			'subject': '_Test Event Web Form',
			'description': '_Test Event Description 1',
			'starts_on': '2014-09-09',
			'name': self.event_name
		}

		self.assertNotEquals(frappe.db.get_value("Event",
			self.event_name, "description"), doc.get('description'))

		accept(web_form='manage-events', data=json.dumps(doc))

		self.assertEquals(frappe.db.get_value("Event",
			self.event_name, "description"), doc.get('description'))
