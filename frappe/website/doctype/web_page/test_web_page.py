from __future__ import unicode_literals
import unittest
import frappe

test_records = frappe.get_test_records('Web Page')

class TestWebPage(unittest.TestCase):
	def test_check_sitemap(self):
		self.assertEquals(frappe.db.get_value("Website Route", 
			{"ref_doctype":"Web Page", "docname": "test-web-page-1"}), "test-web-page-1")
			
		self.assertEquals(frappe.db.get_value("Website Route", 
			{"ref_doctype":"Web Page", "docname": "test-web-page-2"}), "test-web-page-1/test-web-page-2")

		self.assertEquals(frappe.db.get_value("Website Route", 
			{"ref_doctype":"Web Page", "docname": "test-web-page-3"}), "test-web-page-1/test-web-page-3")
			
	def test_check_idx(self):
		self.assertEquals(frappe.db.get_value("Website Route", 
			{"ref_doctype":"Web Page", "docname": "test-web-page-2"}, 'idx'), 0)
		
		self.assertEquals(frappe.db.get_value("Website Route", 
			{"ref_doctype":"Web Page", "docname": "test-web-page-3"}, 'idx'), 1)

		self.assertEquals(frappe.db.get_value("Website Route", 
			{"ref_doctype":"Web Page", "docname": "test-web-page-5"}, 'idx'), 2)
			
	def test_check_rename(self):
		web_page = frappe.get_doc("Web Page", "test-web-page-1")
		web_page.parent_website_route = "test-web-page-4"
		web_page.save()

		self.assertEquals(frappe.db.get_value("Website Route", 
			{"ref_doctype":"Web Page", "docname": "test-web-page-2"}), 
				"test-web-page-4/test-web-page-1/test-web-page-2")
		
		web_page.parent_website_route = ""
		web_page.save()

		self.assertEquals(frappe.db.get_value("Website Route", 
			{"ref_doctype":"Web Page", "docname": "test-web-page-2"}), 
				"test-web-page-1/test-web-page-2")
				
	def test_check_move(self):
		web_page = frappe.get_doc("Web Page", "test-web-page-3")
		web_page.parent_website_route = "test-web-page-4"
		web_page.save()
		
		self.assertEquals(frappe.db.get_value("Website Route", 
			{"ref_doctype":"Web Page", "docname": "test-web-page-2"}, 'idx'), 0)
		
		self.assertEquals(frappe.db.get_value("Website Route", 
			{"ref_doctype":"Web Page", "docname": "test-web-page-3"}, 'idx'), 0)

		self.assertEquals(frappe.db.get_value("Website Route", 
			{"ref_doctype":"Web Page", "docname": "test-web-page-5"}, 'idx'), 1)
		
		web_page = frappe.get_doc("Web Page", "test-web-page-3")
		web_page.parent_website_route = "test-web-page-1"
		web_page.save()