# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json

import nts
from nts.tests.utils import ntsTestCase
from nts.utils import set_request
from nts.website.doctype.web_form.web_form import accept
from nts.website.serve import get_response_content

test_dependencies = ["Web Form"]


class TestWebForm(ntsTestCase):
	def setUp(self):
		nts.conf.disable_website_cache = True

	def tearDown(self):
		nts.conf.disable_website_cache = False

	def test_accept(self):
		nts.set_user("Administrator")

		doc = {
			"doctype": "Event",
			"subject": "_Test Event Web Form",
			"description": "_Test Event Description",
			"starts_on": "2014-09-09",
		}

		accept(web_form="manage-events", data=json.dumps(doc))

		self.event_name = nts.db.get_value("Event", {"subject": "_Test Event Web Form"})
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
			nts.db.get_value("Event", self.event_name, "description"), doc.get("description")
		)

		accept("manage-events", json.dumps(doc))

		self.assertEqual(nts.db.get_value("Event", self.event_name, "description"), doc.get("description"))

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
			self.normalize_html('<meta property="og:image" content="https://nts.io/files/nts.png">'),
			content,
		)
