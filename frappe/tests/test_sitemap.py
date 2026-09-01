import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import get_html_for_route
from frappe.www.sitemap import get_public_pages_from_doctypes


class TestSitemap(IntegrationTestCase):
	def test_sitemap(self):
		xml = get_html_for_route("sitemap.xml")
		self.assertTrue("/about</loc>" in xml)
		self.assertTrue("/contact</loc>" in xml)

	def test_dynamic_routes_excluded(self):
		web_page = frappe.get_doc(
			{
				"doctype": "Web Page",
				"title": "Test Dynamic Sitemap Page",
				"route": "test-dynamic-sitemap/<name>",
				"dynamic_route": 1,
				"published": 1,
				"content_type": "Rich Text",
				"main_section": "test",
			}
		).insert()

		try:
			get_public_pages_from_doctypes.clear_cache()
			xml = get_html_for_route("sitemap.xml")
			self.assertNotIn("test-dynamic-sitemap", xml)
		finally:
			web_page.delete()
			get_public_pages_from_doctypes.clear_cache()
