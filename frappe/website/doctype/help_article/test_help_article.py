# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.tests.utils import FrappeTestCase

# test_records = frappe.get_test_records('Help Article')


class TestHelpArticle(FrappeTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		cls.help_category = frappe.get_doc(
			{
				"doctype": "Help Category",
				"category_name": "_Test Help Category",
			}
		).insert()

		cls.help_article = frappe.get_doc(
			{
				"doctype": "Help Article",
				"title": "_Test Article",
				"category": cls.help_category.name,
				"content": "_Test Article",
			}
		).insert()

	@classmethod
	def tearDownClass(cls) -> None:
		frappe.delete_doc(cls.help_article.doctype, cls.help_article.name)
		frappe.delete_doc(cls.help_category.doctype, cls.help_category.name)
