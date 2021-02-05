import frappe
import os, mimetypes

from werkzeug.wrappers import Response
from werkzeug.wsgi import wrap_file

from frappe.website.render import (resolve_path, build_response)
from frappe.website.redirect import resolve_redirect
from frappe.website.router import get_start_folders
from frappe.website.utils import (get_home_page, can_cache, delete_page_cache,
	get_toc, get_next_link)
from frappe.website.doctype.website_settings.website_settings import get_website_settings

def render(path=None, http_status_code=None):
	"""render html page"""
	if not path:
		path = frappe.local.request.path

	try:
		path = path.strip('/ ')
		resolve_redirect(path)
		path = resolve_path(path)
		data = None

		response = StaticPage(path).get()
		if not response:
			response = TemplatePage(path).get()
		if not response:
			response = DocTypePage(path).get()
		if not response:
			response = TemplatePage('404').get()
	except frappe.PermissionError as e:
		response = TemplatePage('403').get()
	except:
		response = TemplatePage('error').get()

	return response

class WebPage(object):
	def __init__(self, path=None):
		self.headers = None
		self.status_code = 200
		if not path:
			path = frappe.local.request.path
		self.path = path.strip('/ ')

	def get(self):
		if self.validate():
			return self.render()

	def validate(self):
		pass

	def render(self):
		pass

class StaticPage(WebPage):
	def validate(self):
		if ('.' not in self.path):
			return False
		extn = self.path.rsplit('.', 1)[-1]
		if extn in ('html', 'md', 'js', 'xml', 'css', 'txt', 'py', 'json'):
			return False

		if self.find_path_in_apps():
			return True

		return False

	def find_path_in_apps(self):
		for app in frappe.get_installed_apps():
			file_path = frappe.get_app_path(app, 'www') + '/' + self.path
			if os.path.exists(file_path):
				self.file_path = file_path
				return True
		return False

	def render(self):
		try:
			f = open(self.file_path, 'rb')
		except IOError:
			raise NotFound

		response = Response(wrap_file(frappe.local.request.environ, f), direct_passthrough=True)
		response.mimetype = mimetypes.guess_type(self.file_path)[0] or 'application/octet-stream'
		return response

class TemplatePage(WebPage):
	def validate(self):
		for app in frappe.get_installed_apps(frappe_last=True):
			if self.find_page_in_app(app):
				return True

	def find_page_in_app(self, app):
		'''
		Searches for file matching the path in the /www and /templates/pages folders
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
					self.dirname = dirname
					self.file_path = file_path
					self.template_path = os.path.relpath(file_path, self.app_path)
					return True

	def get_index_path_options(self, search_path):
		return (
			search_path,
			search_path + '.html',
			search_path + '.md',
			search_path + '/index.html',
			search_path + '/index.md')

	def render(self):
		return build_response(self.path, self.get_html(), self.status_code, self.headers)

	def get_html(self):
		# context object should be separate from self for security
		# because it will be accessed via the user defined template
		self.context = frappe._dict()

		self.set_pymodule()
		self.setup_template()

		if self.pymodule_name:
			self.update_context()

		if self.source:
			html = frappe.render_template(self.source, self.context)

		elif self.template_path:
			html = self.render_template()

		html = self.update_toc(html)

		return html

	def set_pymodule(self):
		'''
		A template may have a python module with a `get_context` method along with it in the
		same folder. Also the hyphens will be coverted to underscore for python module names.
		This method sets the pymodule_name if it exists.
		'''
		self.basepath = self.template_path.rsplit('.', 1)[0]
		self.pymodule_name = None

		# replace - with _ in the internal modules names
		self.pymodule_path = os.path.join(self.basepath.replace("-", "_") + ".py")

		if os.path.exists(os.path.join(self.app_path, self.pymodule_path)):
			self.pymodule_name = self.app + "." + self.pymodule_path.replace(os.path.sep, ".")[:-3]

	def setup_template(self):
		'''Setup template source, frontmatter and markdown conversion'''
		self.source = self.get_raw_template()

		if self.template_path.endswith(('.md', '.html')):
			self.extract_frontmatter()

		self.convert_from_markdown()

		if self.extends_template():
			self.context.base_template_path = self.context.base_template_path or 'templates/base.html'
		else:
			self.source = None # clear the source

		# TODO: setup index.txt ?

	def update_context(self):
		self.set_page_properties()
		self.context.update(get_website_settings(self.context))
		self.context.update(frappe.local.conf.get("website_context") or {})

		self.pymodule = frappe.get_module(self.pymodule_name)

		if self.pymodule:
			self.set_pymodule_properties()

			data = self.run_pymodule_method('get_context')
			# some methods may return a "context" object
			if data: self.context.update(data)

			# TODO: self.context.children = self.run_pymodule_method('get_children')

		self.context.developer_mode = frappe.conf.developer_mode

	def set_pymodule_properties(self):
		for prop in ("base_template_path", "template", "no_cache", "sitemap",
			"condition_field"):
			if hasattr(self.pymodule, prop):
				self.context[prop] = getattr(self.pymodule, prop)

	def set_page_properties(self):
		self.context.template = self.template_path

	def run_pymodule_method(self, method):
		if hasattr(self.pymodule, method):
			try:
				return getattr(self.pymodule, method)(self)
			except (frappe.PermissionError, frappe.DoesNotExistError, frappe.Redirect):
				raise
			except:
				if not frappe.flags.in_migrate:
					frappe.errprint(frappe.utils.get_traceback())

	def render_template(self):
		if self.path.endswith('min.js'):
			# directly serve min.js pages using the jloader to find it in various apps
			# (can be used as static?)
			html = self.get_raw_template()
		else:
			html = frappe.get_template(self.template_path).render(self.context)

	def extends_template(self):
		return (self.template_path.endswith(('.html', '.md', ))
			and ('{%- extends' in self.source
				or '{% extends' in self.source))

	def get_raw_template(self):
		return frappe.get_jloader().get_source(frappe.get_jenv(), self.template_path)[0]

	def load_colocated_files(self):
		'''load co-located css/js files with the same name'''
		js_path = self.basepath + '.js'
		if os.path.exists(js_path) and '{% block script %}' not in self.source:
			self.colocated_js = self.get_colocated_file(js_path)

		css_path = self.basepath + '.css'
		if os.path.exists(css_path) and '{% block style %}' not in self.source:
			self.colocated_css = self.get_colocated_file(css_path)

	def get_colocated_file(self, path):
		with io.open(path, 'r', encoding = 'utf-8') as f:
			return f.read()

	def extract_frontmatter(self):
		try:
			# values will be used to update page_info
			res = get_frontmatter(self.source)
			if res['attributes']:
				self.context.update(res['attributes'])
				self.source = res['body']
		except Exception:
			pass

	def convert_from_markdown(self):
		if self.template_path.endswith('.md'):
			self.source = frappe.utils.md_to_html(self.source)
			self.page_toc_html = self.toc_html

			if not self.show_sidebar:
				self.source = '<div class="from-markdown">' + self.source + '</div>'

	def update_toc(self, html):
		if '{index}' in html:
			html = html.replace('{index}', get_toc(self.path))

		if '{next}' in html:
			html = html.replace('{next}', get_next_link(self.path))

		return html


class DocTypePage(WebPage):
	pass

class WebFormPage(WebPage):
	pass

