import mimetypes
import os

from werkzeug.wrappers import Response
from werkzeug.wsgi import wrap_file

import frappe
from frappe import _
from frappe.utils import cint, cstr
from frappe.model.document import get_controller
from frappe.website.doctype.website_settings.website_settings import \
	get_website_settings
from frappe.website.redirect import resolve_redirect
from frappe.website.render import build_response, resolve_path
from frappe.website.router import (get_doctypes_with_web_view,
	get_page_info_from_web_page_with_dynamic_routes, get_start_folders)
from frappe.website.utils import (can_cache, delete_page_cache, get_home_page,
	get_next_link, get_toc)


def get_response(path=None, http_status_code=200):
	"""render html page"""
	query_string = None
	if not path:
		path = frappe.local.request.path
		query_string = frappe.local.request.query_string

	try:
		path = path.strip('/ ')
		resolve_redirect(path, query_string)
		path = resolve_path(path)
		data = None

		# there is no way to determine the type of the page based on the route
		# so evaluate each type of page sequentially
		response = StaticPage(path, http_status_code).get()
		if not response:
			response = TemplatePage(path, http_status_code).get()
		if not response:
			response = ListPage(path, http_status_code).get()
		if not response:
			response = DocumentPage(path, http_status_code).get()
		if not response:
			response = PrintPage(path, http_status_code).get()
		if not response:
			response = TemplatePage('404', 404).get()
	except frappe.Redirect:
		return build_response(path, "", 301, {
			"Location": frappe.flags.redirect_location or (frappe.local.response or {}).get('location'),
			"Cache-Control": "no-store, no-cache, must-revalidate"
		})
	except frappe.PermissionError as e:
		frappe.local.message = cstr(e)
		response = NotPermittedPage(path, http_status_code).get()
	except Exception as e:
		response = TemplatePage('error', getattr(e, 'http_status_code', None) or http_status_code).get()

	return response

class WebPage(object):
	def __init__(self, path=None, http_status_code=None):
		self.headers = None
		self.http_status_code = http_status_code or 200
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

class BaseTemplatePage(WebPage):
	def init_context(self):
		self.context = frappe._dict()
		self.context.update(get_website_settings(self.context))
		self.context.update(frappe.local.conf.get("website_context") or {})

	def add_csrf_token(self, html):
		if frappe.local.session:
			return html.replace("<!-- csrf_token -->", '<script>frappe.csrf_token = "{0}";</script>'.format(
					frappe.local.session.data.csrf_token))
		else:
			return html

	def post_process_context(self):
		self.add_metatags()
		# add_sidebar_and_breadcrumbs(context)

		self.set_base_template_if_missing()
		self.set_title_with_prefix()
		self.update_website_context()

		# set using frappe.respond_as_web_page
		if hasattr(frappe.local, 'response') and frappe.local.response.get('context'):
			self.context.update(frappe.local.response.context)

		# to be able to inspect the context dict
		# Use the macro "inspect" from macros.html
		self.context._context_dict = self.context

		# context sends us a new template path
		if self.context.template:
			self.template_path = self.context.template


	def set_base_template_if_missing(self):
		if not self.context.base_template_path:
			app_base = frappe.get_hooks("base_template")
			self.context.base_template_path = app_base[-1] if app_base else "templates/base.html"

	def set_title_with_prefix(self):
		if (self.context.title_prefix and self.context.title
			and not self.context.title.startswith(self.context.title_prefix)):
			self.context.title = '{0} - {1}'.format(self.context.title_prefix, self.context.title)

	def update_website_context(self):
		# apply context from hooks
		update_website_context = frappe.get_hooks('update_website_context')
		for method in update_website_context:
			values = frappe.get_attr(method)(self.context)
			if values:
				self.context.update(values)

	def add_metatags(self):
		self.tags = frappe._dict(self.context.get("metatags") or {})
		self.init_metatags_from_context()
		self.set_opengraph_tags()
		self.set_twitter_tags()
		self.set_meta_published_on()
		self.set_metatags_from_website_route_meta()

		self.context.metatags = self.tags

	def init_metatags_from_context(self):
		for key in ('title', 'description', 'image', 'author', 'url', 'published_on'):
			if not key in self.tags and self.context.get(key):
				self.tags[key] = self.context[key]

		if not self.tags.get('title'): self.tags['title'] = self.context.get('name')

		if self.tags.get('image'):
			self.tags['image'] = frappe.utils.get_url(self.tags['image'])

		self.tags["language"] = frappe.local.lang or "en"

	def set_opengraph_tags(self):
		if "og:type" not in self.tags:
			self.tags["og:type"] = "article"

		for key in ('title', 'description', 'image', 'author', 'url'):
			if self.tags.get(key):
				self.tags['og:' + key] = self.tags.get(key)

	def set_twitter_tags(self):
		for key in ('title', 'description', 'image', 'author', 'url'):
			if self.tags.get(key):
				self.tags['twitter:' + key] = self.tags.get(key)

		if self.tags.get('image'):
			self.tags['twitter:card'] = "summary_large_image"
		else:
			self.tags["twitter:card"] = "summary"

	def set_meta_published_on(self):
		if "published_on" in self.tags:
			self.tags["datePublished"] = self.tags["published_on"]
			del self.tags["published_on"]

	def set_metatags_from_website_route_meta(self):
		'''
		Get meta tags from Website Route meta
		they can override the defaults set above
		'''
		route = self.context.path
		if route == '':
			# homepage
			route = frappe.db.get_single_value('Website Settings', 'home_page')

		route_exists = (route
			and not route.endswith(('.js', '.css'))
			and frappe.db.exists('Website Route Meta', route))

		if route_exists:
			website_route_meta = frappe.get_doc('Website Route Meta', route)
			for meta_tag in website_route_meta.meta_tags:
				d = meta_tag.get_meta_dict()
				self.tags.update(d)

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
		self.update_context()
		self.post_process_context()
		self.setup_template()
		html = self.render_template()

		html = self.update_toc(html)
		html = self.add_csrf_token(html)

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

		if self.pymodule_name:
			self.pymodule = frappe.get_module(self.pymodule_name)
			self.set_pymodule_properties()

			data = self.run_pymodule_method('get_context')

			# some methods may return a "context" object
			if data: self.context.update(data)

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

	def run_pymodule_method(self, method):
		if hasattr(self.pymodule, method):
			try:
				return getattr(self.pymodule, method)(self.context)
			except (frappe.PermissionError, frappe.DoesNotExistError, frappe.Redirect):
				raise
			except:
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

	def set_standard_path(self, path):
		self.app = 'frappe'
		self.app_path = frappe.get_app_path('frappe')
		self.path = path
		self.template_path = 'www/{path}.html'.format(path=path)


class ListPage(TemplatePage):
	def validate(self):
		if frappe.db.get_value('DocType', self.path):
			frappe.local.form_dict.doctype = self.path
			self.set_standard_path('list')
			return True
		return False

class PrintPage(TemplatePage):
	'''
	default path returns a printable object (based on permission)
	/Quotation/Q-0001
	'''
	def validate(self):
		parts = self.path.split('/', 1)
		if len(parts)==2:
			if (frappe.db.get_value('DocType', parts[0])
				and frappe.db.get_value(parts[0], parts[1])):
				frappe.form_dict.doctype = parts[0]
				frappe.form_dict.name = parts[1]
				self.set_standard_path('printview')
				return True

		return False

class NotPermittedPage(TemplatePage):
	def validate(self):
		frappe.local.message_title = _("Not Permitted")
		frappe.local.response['context'] = dict(
			indicator_color = 'red',
			primary_action = '/login',
			primary_label = _('Login'),
			fullpage=True
		)
		self.set_standard_path('message')
		return True

class DocumentPage(BaseTemplatePage):
	def validate(self):
		'''
		Find a document with matching `route` from all doctypes with `has_web_view`=1
		'''
		if self.search_in_doctypes_with_web_view():
			return True

		if self.search_web_page_dynamic_routes():
			return True

		return False

	def search_in_doctypes_with_web_view(self):
		for doctype in get_doctypes_with_web_view():
			filters = dict(route=self.path)
			meta = frappe.get_meta(doctype)
			condition_field = self.get_condition_field(meta)

			if condition_field:
				filters[condition_field] = 1

			try:
				self.docname = frappe.db.get_value(doctype, filters, 'name')
				if self.docname:
					self.doctype = doctype
					self.meta = meta
					return True
			except Exception as e:
				if not frappe.db.is_missing_column(e): raise e

	def search_web_page_dynamic_routes(self):
		d = get_page_info_from_web_page_with_dynamic_routes(self.path)
		if d:
			self.doctype = 'Web Page'
			self.docname = d.name
			self.meta = frappe.get_meta(self.doctype)
			return True
		else:
			return False

	def render(self):
		self.doc = frappe.get_doc(self.doctype, self.docname)
		self.init_context()
		self.update_context()
		self.post_process_context()

		html = frappe.get_template(self.context.template_path).render(self.context)
		html = self.add_csrf_token(html)

		return build_response(self.path, html, self.http_status_code or 200, self.headers)

	def update_context(self):
		self.context.doc = self.doc
		self.context.update(self.context.doc.as_dict())
		self.context.update(self.context.doc.get_website_properties())

		if not self.context.template_path:
			self.context.template_path = self.context.doc.meta.get_web_template()

		if hasattr(self.doc, "get_context"):
			ret = self.doc.get_context(self.context)

			if ret:
				self.context.update(ret)

		for prop in ("no_cache", "sitemap"):
			if not prop in self.context:
				self.context[prop] = getattr(self.doc, prop, False)

	def get_condition_field(self, meta):
		condition_field = None
		if meta.is_published_field:
			condition_field = meta.is_published_field
		elif not meta.custom:
			controller = get_controller(meta.doctype)
			condition_field = controller.website.condition_field

		return condition_field

class WebFormPage(WebPage):
	pass
