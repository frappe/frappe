from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.website.doctype.help_article import help_article
from frappe.www import portal


class TestPortalList(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		category = frappe.get_doc(doctype="Help Category", category_name="Test Portal Category").insert()
		cls.article = frappe.get_doc(
			doctype="Help Article",
			title="Test Portal Article",
			category=category.name,
			content="content",
			published=1,
		).insert()

	def setUp(self):
		self.form_dict = frappe.local.form_dict
		self.path = getattr(frappe.local, "path", None)
		frappe.local.form_dict = frappe._dict(doctype="Help Article")
		frappe.local.path = "kb"

	def tearDown(self):
		frappe.local.form_dict = self.form_dict
		if self.path is None:
			del frappe.local.path
		else:
			frappe.local.path = self.path

	def test_list_context_is_resolved_once_per_render(self):
		with patch.object(
			help_article, "get_list_context", wraps=help_article.get_list_context
		) as get_list_context:
			context = portal.get_context(frappe._dict(), doctype="Help Article")

		get_list_context.assert_called_once()
		self.assertTrue(context.row_template.endswith("help_article_row.html"))
		self.assertTrue(any(self.article.route in row for row in context.result))

	def test_page_context_does_not_leak_into_rows(self):
		def get_list_context_returning_page_context(context):
			context.row_template = "website/doctype/web_page/templates/web_page_row.html"
			return context

		with patch.object(help_article, "get_list_context", get_list_context_returning_page_context):
			context = portal.get_context(frappe._dict(title="Knowledge Base", name="kb"))

		self.assertTrue(any(self.article.title in row for row in context.result))

	def test_list_context_is_not_taken_from_query_params(self):
		frappe.local.form_dict.list_context = "injected"
		context = portal.get_context(frappe._dict(), doctype="Help Article")
		self.assertTrue(any(self.article.route in row for row in context.result))
