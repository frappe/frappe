# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE
from bs4 import BeautifulSoup

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request
from frappe.website.serve import get_response


class TestWebTemplate(IntegrationTestCase):
	def test_render_web_template_with_values(self):
		doc = frappe.get_doc("Web Template", "Hero with Right Image")
		values = {
			"title": "Test Hero",
			"subtitle": "Test subtitle content",
			"primary_action": "/test",
			"primary_action_label": "Test Button",
		}
		html = doc.render(values)

		soup = BeautifulSoup(html, "html.parser")
		heading = soup.find("h1")
		self.assertTrue("Test Hero" in heading.text)

		subtitle = soup.find("p")
		self.assertTrue("Test subtitle content" in subtitle.text)

		button = soup.find("a")
		self.assertTrue("Test Button" in button.text)
		self.assertTrue("/test" == button.attrs["href"])

	def test_web_page_with_page_builder(self):
		self.create_web_page()

		set_request(method="GET", path="test-web-template")
		response = get_response()

		self.assertEqual(response.status_code, 200)

		html = frappe.safe_decode(response.get_data())

		soup = BeautifulSoup(html, "html.parser")
		sections = soup.find("main").find_all("section")

		self.assertEqual(len(sections), 2)
		self.assertEqual(sections[0].find("h2").text, "Test Title")
		self.assertEqual(sections[0].find("p").text, "test lorem ipsum")
		self.assertEqual(len(sections[1].find_all("a")), 3)

	def test_custom_stylesheet(self):
		self.create_web_page()
		theme = self.create_website_theme()
		theme.set_as_default()

		frappe.conf.developer_mode = 1

		set_request(method="GET", path="test-web-template")
		response = get_response()
		self.assertEqual(response.status_code, 200)
		html = frappe.safe_decode(response.get_data())

		soup = BeautifulSoup(html, "html.parser")
		stylesheet = soup.select_one('link[rel="stylesheet"]')

		self.assertEqual(stylesheet.attrs["href"], theme.theme_url)

		frappe.get_doc("Website Theme", "Standard").set_as_default()

	def create_web_page(self):
		if not frappe.db.exists("Web Page", "test-web-template"):
			frappe.get_doc(
				{
					"doctype": "Web Page",
					"title": "test-web-template",
					"name": "test-web-template",
					"published": 1,
					"route": "test-web-template",
					"content_type": "Page Builder",
					"page_blocks": [
						{
							"web_template": "Section with Image",
							"web_template_values": frappe.as_json(
								{"title": "Test Title", "subtitle": "test lorem ipsum"}
							),
						},
						{
							"web_template": "Section with Cards",
							"web_template_values": frappe.as_json(
								{
									"title": "Test Title",
									"subtitle": "test lorem ipsum",
									"card_size": "Medium",
									"card_1_title": "Card 1 Title",
									"card_1_content": "Card 1 Content",
									"card_1_url": "/card1url",
									"card_2_title": "Card 2 Title",
									"card_2_content": "Card 2 Content",
									"card_2_url": "/card2url",
									"card_3_title": "Card 3 Title",
									"card_3_content": "Card 3 Content",
									"card_3_url": "/card3url",
								}
							),
						},
					],
				}
			).insert()

	def create_website_theme(self):
		if not frappe.db.exists("Website Theme", "Custom"):
			theme = frappe.get_doc({"doctype": "Website Theme", "theme": "Custom"}).insert()
		else:
			theme = frappe.get_doc("Website Theme", "Custom")
		return theme
