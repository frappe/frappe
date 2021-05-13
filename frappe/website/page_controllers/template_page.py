import io
import os

import frappe
from frappe.website.page_controllers.base_template_page import BaseTemplatePage
from frappe.website.context import add_sidebar_and_breadcrumbs
from frappe.website.render import build_response
from frappe.website.router import get_base_template
from frappe.website.utils import (extract_comment_tag, extract_title,
	get_next_link, get_toc)


class TemplatePage(BaseTemplatePage):
	def validate(self):
		for app in frappe.get_installed_apps(frappe_last=True):
			if self.find_page_in_app(app):
				return True

	def find_page_in_app(self, app):
		'''
		Searches for file matching the path in the /www
		and /templates/pages folders
		'''
		app_path = frappe.get_app_path(app)
		folders = get_start_folders()

		for dirname in folders:
			search_path = os.path.join(app_path, dirname, self.path)
			for p in self.get_index_path_options(search_path):
				file_path = frappe.as_unicode(p)
				if os.path.exists(file_path) and not os.path.isdir(file_path):
					self.app = app
					self.app_path = app_path
					self.template_path = os.path.relpath(file_path, self.app_path)
					self.basepath = os.path.dirname(file_path)
					return True

	def get_index_path_options(self, search_path):
		return (
			search_path,
			search_path + '.html',
			search_path + '.md',
			search_path + '/index.html',
			search_path + '/index.md')

	def render(self):
		return build_response(self.path, self.get_html(), self.http_status_code, self.headers)

	def get_html(self):
		# context object should be separate from self for security
		# because it will be accessed via the user defined template
		self.init_context()

		self.set_pymodule()
		self.setup_template()
		self.update_context()
		self.post_process_context()
		html = self.render_template()

		html = self.update_toc(html)
		html = self.add_csrf_token(html)

		return html

	def post_process_context(self):
		self.add_sidebar_and_breadcrumbs()
		self.set_missing_values()
		super(TemplatePage, self).post_process_context()

	def add_sidebar_and_breadcrumbs(self):
		add_sidebar_and_breadcrumbs(self.context)

	def set_pymodule(self):
		'''
		A template may have a python module with a `get_context` method along with it in the
		same folder. Also the hyphens will be coverted to underscore for python module names.
		This method sets the pymodule_name if it exists.
		'''
		template_basepath = os.path.splitext(self.template_path)[0]
		self.pymodule_name = None

		# replace - with _ in the internal modules names
		self.pymodule_path = os.path.join(template_basepath.replace("-", "_") + ".py")

		if os.path.exists(os.path.join(self.app_path, self.pymodule_path)):
			self.pymodule_name = self.app + "." + self.pymodule_path.replace(os.path.sep, ".")[:-3]

	def setup_template(self):
		'''Setup template source, frontmatter and markdown conversion'''
		self.source = self.get_raw_template()
		self.extract_frontmatter()
		self.convert_from_markdown()

	def update_context(self):
		self.context.base_template = self.context.base_template or get_base_template(self.path)
		self.context.basepath = self.basepath
		self.context.path = self.path
		self.set_page_properties()
		self.set_properties_from_source()
		self.load_colocated_files()
		self.context.build_version = frappe.utils.get_build_version()

		if self.pymodule_name:
			self.pymodule = frappe.get_module(self.pymodule_name)
			self.set_pymodule_properties()

			data = self.run_pymodule_method('get_context')
			# some methods may return a "context" object
			if data:
				self.context.update(data)
			# TODO: self.context.children = self.run_pymodule_method('get_children')

		self.context.developer_mode = frappe.conf.developer_mode
		if self.context.http_status_code:
			self.http_status_code = self.context.http_status_code

	def set_pymodule_properties(self):
		for prop in ("base_template_path", "template", "no_cache", "sitemap",
			"condition_field"):
			if hasattr(self.pymodule, prop):
				self.context[prop] = getattr(self.pymodule, prop)

	def set_page_properties(self):
		self.context.template = self.template_path
		self.context.base_template = self.context.base_template or 'templates/web.html'

	def set_properties_from_source(self):
		if not self.source:
			return
		context = self.context
		if not context.title:
			context.title = extract_title(self.source, self.path)

		base_template = extract_comment_tag(self.source, 'base_template')
		if base_template:
			context.base_template = base_template

		if (context.base_template
			and "{%- extends" not in self.source
			and "{% extends" not in self.source
			and "</body>" not in self.source):
			self.source = '''{{% extends "{0}" %}}
				{{% block page_content %}}{1}{{% endblock %}}'''.format(context.base_template, self.source)

	def run_pymodule_method(self, method):
		if hasattr(self.pymodule, method):
			try:
				return getattr(self.pymodule, method)(self.context)
			except (frappe.PermissionError, frappe.DoesNotExistError, frappe.Redirect):
				raise
			except Exception:
				if not frappe.flags.in_migrate:
					frappe.errprint(frappe.utils.get_traceback())

	def render_template(self):
		if self.source:
			html = frappe.render_template(self.source, self.context)
		elif self.template_path:
			if self.path.endswith('min.js'):
				html = self.get_raw_template() # static
			else:
				html = frappe.get_template(self.template_path).render(self.context)

		return html

	def extends_template(self):
		return (self.template_path.endswith(('.html', '.md'))
			and ('{%- extends' in self.source
				or '{% extends' in self.source))

	def get_raw_template(self):
		return frappe.get_jloader().get_source(frappe.get_jenv(), self.template_path)[0]

	def load_colocated_files(self):
		'''load co-located css/js files with the same name'''
		js_path = self.basepath + '.js'
		if os.path.exists(js_path) and '{% block script %}' not in self.source:
			self.context.colocated_js = self.get_colocated_file(js_path)

		css_path = self.basepath + '.css'
		if os.path.exists(css_path) and '{% block style %}' not in self.source:
			self.context.colocated_css = self.get_colocated_file(css_path)

	def get_colocated_file(self, path):
		with io.open(path, 'r', encoding = 'utf-8') as f:
			return f.read()

	def extract_frontmatter(self):
		if not self.template_path.endswith(('.md', '.html')):
			return

		try:
			# values will be used to update self
			res = get_frontmatter(self.source)
			if res['attributes']:
				self.context.update(res['attributes'])
				self.source = res['body']
		except Exception:
			pass

	def convert_from_markdown(self):
		if self.template_path.endswith('.md'):
			self.source = frappe.utils.md_to_html(self.source)
			self.context.page_toc_html = self.source.toc_html

			if not self.context.show_sidebar:
				self.source = '<div class="from-markdown">' + self.source + '</div>'

	def update_toc(self, html):
		if '{index}' in html:
			html = html.replace('{index}', get_toc(self.path))

		if '{next}' in html:
			html = html.replace('{next}', get_next_link(self.path))

		return html

	def set_standard_path(self, path):
		self.app = 'frappe'
		self.app_path = frappe.get_app_path('frappe')
		self.path = path
		self.template_path = 'www/{path}.html'.format(path=path)

	def set_missing_values(self):
		if "url_prefix" not in self.context:
			self.context.url_prefix = ""

		if self.context.url_prefix and self.context.url_prefix[-1]!='/':
			self.context.url_prefix += '/'

		self.context.path = self.path
		self.context.pathname = frappe.local.path

		# for backward compatibility
		self.context.docs_base_url = '/docs'


def get_start_folders():
	return frappe.local.flags.web_pages_folders or ('www', 'templates/pages')

def get_frontmatter(string):
	"""
	Reference: https://github.com/jonbeebe/frontmatter
	"""
	import re

	import yaml

	fmatter = ""
	body = ""
	result = re.compile(r'^\s*(?:---|\+\+\+)(.*?)(?:---|\+\+\+)\s*(.+)$', re.S | re.M).search(string)

	if result:
		fmatter = result.group(1)
		body = result.group(2)

	return {
		"attributes": yaml.safe_load(fmatter),
		"body": body,
	}
