import frappe
from frappe.core.doctype.user.test_user import test_user
from frappe.tests import IntegrationTestCase
from frappe.website.path_resolver import PathResolver
from frappe.website.serve import get_response_content


def make_web_page(**values):
	title = frappe.generate_hash(length=10)
	return frappe.get_doc(
		{
			"doctype": "Web Page",
			"title": title,
			"route": title,
			"published": 1,
			"content_type": "HTML",
			**values,
		}
	).insert()


class TestWebPage(IntegrationTestCase):
	def setUp(self):
		frappe.db.delete("Web Page")
		for t in self.globalTestRecords["Web Page"]:
			frappe.get_doc(t).insert()

	def test_path_resolver(self):
		self.assertTrue(PathResolver("test-web-page-1").is_valid_path())
		self.assertTrue(PathResolver("test-web-page-1/test-web-page-2").is_valid_path())
		self.assertTrue(PathResolver("test-web-page-1/test-web-page-3").is_valid_path())
		self.assertFalse(PathResolver("test-web-page-1/test-web-page-Random").is_valid_path())

	def test_content_type(self):
		web_page = frappe.get_doc(
			doctype="Web Page",
			title="Test Content Type",
			published=1,
			content_type="Rich Text",
			main_section="rich text",
			main_section_md="# h1\nmarkdown content",
			main_section_html="<div>html content</div>",
		).insert()

		self.assertIn("rich text", get_response_content("/test-content-type"))

		web_page.content_type = "Markdown"
		web_page.save()
		self.assertIn("markdown content", get_response_content("/test-content-type"))

		web_page.content_type = "HTML"
		web_page.save()
		self.assertIn("html content", get_response_content("/test-content-type"))

		web_page.delete()

	def test_dynamic_route(self):
		web_page = frappe.get_doc(
			doctype="Web Page",
			title="Test Dynamic Route",
			published=1,
			dynamic_route=1,
			route="/doctype-view/<doctype>",
			content_type="HTML",
			dynamic_template=1,
			main_section_html="<div>{{ frappe.form_dict.doctype }}</div>",
		).insert()
		try:
			from frappe.utils import get_html_for_route

			content = get_html_for_route("/doctype-view/DocField")
			self.assertIn("<div>DocField</div>", content)
		finally:
			web_page.delete()

	def test_jinja_content_needs_code_author(self):
		jinja_page = make_web_page(main_section_html="<p>{{ 6 * 7 }}</p>")
		markdown_page = make_web_page(content_type="Markdown", main_section_md="plain")
		make_web_page(dynamic_template=1, main_section_html="<p>dynamic</p>")
		escaped_markdown = r"\{\{ 6 * 7 \}\}"
		make_web_page(content_type="Markdown", main_section_md=escaped_markdown)

		with test_user(roles=["Website Manager"]) as user, self.set_user(user.name):
			static_page = make_web_page(main_section_html="<p>About</p>")
			static_page.main_section_html = "<p>About us</p>"
			static_page.save()

			# without `{{` this only renders as Jinja on a dynamic page
			content = "<p>{% if 1 %}x{% endif %}</p>"
			make_web_page(main_section_html=content)
			self.assertRaises(
				frappe.PermissionError, make_web_page, dynamic_template=1, main_section_html=content
			)

			# Markdown renders escaped braces as `{{`; an unchanged copy still saves
			make_web_page(content_type="Markdown", main_section_md=escaped_markdown)
			self.assertRaises(
				frappe.PermissionError,
				make_web_page,
				content_type="Markdown",
				main_section_md=r"\{\{ frappe.session.user \}\}",
			)

			# the Markdown page keeps HTML in an inactive field that content_type could switch on
			for page in (jinja_page, markdown_page):
				with self.subTest(page=page.content_type):
					page = frappe.get_doc("Web Page", page.name)
					page.main_section_html = "<p>{{ frappe.session.user }}</p>"
					self.assertRaises(frappe.PermissionError, page.save)
