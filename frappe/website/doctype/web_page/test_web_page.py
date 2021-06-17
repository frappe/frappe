
import unittest
import frappe
from frappe.website.path_resolver import PathResolver
from frappe.website.serve import get_response_content

test_records = frappe.get_test_records('Web Page')

class TestWebPage(unittest.TestCase):
	def setUp(self):
		frappe.db.sql("delete from `tabWeb Page`")
		for t in test_records:
			frappe.get_doc(t).insert()

	def test_path_resolver(self):
		self.assertTrue(PathResolver("test-web-page-1").is_valid_path())
		self.assertTrue(PathResolver("test-web-page-1/test-web-page-2").is_valid_path())
		self.assertTrue(PathResolver("test-web-page-1/test-web-page-3").is_valid_path())
		self.assertFalse(PathResolver("test-web-page-1/test-web-page-Random").is_valid_path())

	def test_base_template(self):
		content = get_response_content('/_test/_test_custom_base.html')

		# assert the text in base template is rendered
		self.assertIn('<h1>This is for testing</h1>', content)

		# assert template block rendered
		self.assertIn('<p>Test content</p>', content)

	def test_content_type(self):
		web_page = frappe.get_doc(dict(
			doctype = 'Web Page',
			title = 'Test Content Type',
			published = 1,
			content_type = 'Rich Text',
			main_section = 'rich text',
			main_section_md = '# h1\nmarkdown content',
			main_section_html = '<div>html content</div>'
		)).insert()

		self.assertIn('rich text', get_response_content('/test-content-type'))

		web_page.content_type = 'Markdown'
		web_page.save()
		self.assertIn('markdown content', get_response_content('/test-content-type'))

		web_page.content_type = 'HTML'
		web_page.save()
		self.assertIn('html content', get_response_content('/test-content-type'))

		web_page.delete()

	def test_dynamic_route(self):
		web_page = frappe.get_doc(dict(
			doctype = 'Web Page',
			title = 'Test Dynamic Route',
			published = 1,
			dynamic_route = 1,
			route = '/doctype-view/<doctype>',
			content_type = 'HTML',
			dynamic_template = 1,
			main_section_html = '<div>{{ frappe.form_dict.doctype }}</div>'
		)).insert()
		try:
			from frappe.utils import get_html_for_route
			content = get_html_for_route('/doctype-view/DocField')
			self.assertIn('<div>DocField</div>', content)
		finally:
			web_page.delete()

	def test_custom_base_template_path(self):
		content = get_response_content('/_test/_test_folder/_test_page')
		# assert the text in base template is rendered
		self.assertIn('<h1>This is for testing</h1>', content)

		# assert template block rendered
		self.assertIn('<p>Test content</p>', content)

	def test_json_sidebar_data(self):
		frappe.flags.look_for_sidebar = False
		content = get_response_content('/_test/_test_folder/_test_page')
		self.assertNotIn('Test Sidebar', content)
		frappe.flags.look_for_sidebar = True
		content = get_response_content('/_test/_test_folder/_test_page')
		self.assertIn('Test Sidebar', content)
		frappe.flags.look_for_sidebar = False

	def test_index_and_next_comment(self):
		content = get_response_content('/_test/_test_folder')
		# test if {index} was rendered
		self.assertIn('<a href="/_test/_test_folder/_test_page"> Test Page</a>', content)

		self.assertIn('<a href="/_test/_test_folder/_test_toc">Test TOC</a>', content)

		content = get_response_content('/_test/_test_folder/_test_page')
		# test if {next} was rendered
		self.assertIn('Next: <a class="btn-next" href="/_test/_test_folder/_test_toc">Test TOC</a>', content)

	def test_colocated_assets(self):
		content = get_response_content('/_test/_test_folder/_test_page')
		self.assertIn("<script>console.log('test data');</script>", content)
		self.assertIn("background-color: var(--bg-color);", content)

	def test_breadcrumbs(self):
		content = get_response_content('/_test/_test_folder/_test_page')
		self.assertIn('<span itemprop="name">Test TOC</span>', content)
		self.assertIn('<span itemprop="name"> Test Page</span>', content)

		content = get_response_content('/_test/_test_folder/index')
		self.assertIn('<span itemprop="name"> Test</span>', content)
		self.assertIn('<span itemprop="name">Test TOC</span>', content)

	def test_downloadable_file(self):
		pass
