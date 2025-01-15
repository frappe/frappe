import os
from importlib.machinery import all_suffixes

import click

import frappe
from frappe.website.page_renderers.base_template_page import BaseTemplatePage
from frappe.website.router import get_base_template, get_page_info
from frappe.website.utils import (
	cache_html,
	extract_comment_tag,
	extract_title,
	get_frontmatter,
	get_next_link,
	get_sidebar_items,
	get_toc,
	is_binary_file,
)

PY_LOADER_SUFFIXES = tuple(all_suffixes())

WEBPAGE_PY_MODULE_PROPERTIES = (
	"base_template_path",
	"template",
	"no_cache",
	"sitemap",
	"condition_field",
)

COMMENT_PROPERTY_KEY_VALUE_MAP = {
	"no-breadcrumbs": ("no_breadcrumbs", 1),
	"show-sidebar": ("show_sidebar", 1),
	"add-breadcrumbs": ("add_breadcrumbs", 1),
	"no-header": ("no_header", 1),
	"add-next-prev-links": ("add_next_prev_links", 1),
	"no-cache": ("no_cache", 1),
	"no-sitemap": ("sitemap", 0),
	"sitemap": ("sitemap", 1),
}


class TemplatePage(BaseTemplatePage):
	def __init__(self, path, http_status_code=None):
		super().__init__(path=path, http_status_code=http_status_code)
		self.set_template_path()

	def set_template_path(self):
		"""
		Searches for file matching the path in the /www
		and /templates/pages folders and sets path if match is found
		"""
		folders = get_start_folders()
		for app in reversed(frappe.get_installed_apps()):
			app_path = frappe.get_app_path(app)

			for dirname in folders:
				search_path = os.path.join(app_path, dirname, self.path)
				for file_path in self.get_index_path_options(search_path):
					if os.path.isfile(file_path) and not is_binary_file(file_path):
						self.app = app
						self.app_path = app_path
						self.file_dir = dirname
						self.basename = os.path.splitext(file_path)[0]
						self.template_path = os.path.relpath(file_path, self.app_path)
						self.basepath = os.path.dirname(file_path)
						self.filename = os.path.basename(file_path)
						self.name = os.path.splitext(self.filename)[0]
						return

	def can_render(self):
		return (
			hasattr(self, "template_path")
			and self.template_path
			and not self.template_path.endswith(PY_LOADER_SUFFIXES)
		)

	@staticmethod
	def get_index_path_options(search_path):
		return (
			frappe.as_unicode(f"{search_path}{d}") for d in ("", ".html", ".md", "/index.html", "/index.md")
		)

	def render(self):
		html = self.get_html()
		html = self.add_csrf_token(html)
		return self.build_response(html)

	@cache_html
	def get_html(self):
		# context object should be separate from self for security
		# because it will be accessed via the user defined template
		self.init_context()

		self.set_pymodule()
		self.update_context()
		self.setup_template_source()
		self.load_colocated_files()
		self.set_properties_from_source()
		self.post_process_context()

		html = self.render_template()
		html = self.update_toc(html)

		return html

	def post_process_context(self):
		self.set_user_info()
		self.add_sidebar_and_breadcrumbs()
		super().post_process_context()

	def add_sidebar_and_breadcrumbs(self):
		if not self.context.sidebar_items:
			self.context.sidebar_items = get_sidebar_items(self.context.website_sidebar, self.basepath)

		if self.context.add_breadcrumbs and not self.context.parents:
			parent_path = os.path.dirname(self.path)
			if self.path.endswith("index"):
				# in case of index page move one directory up for parent path
				parent_path = os.path.dirname(parent_path)

			for parent_file_path in self.get_index_path_options(parent_path):
				parent_file_path = os.path.join(self.app_path, self.file_dir, parent_file_path)
				if os.path.isfile(parent_file_path):
					parent_page_context = get_page_info(parent_file_path, self.app, self.file_dir)
					if parent_page_context:
						self.context.parents = [
							dict(route=os.path.dirname(self.path), title=parent_page_context.title)
						]
					break

	def set_pymodule(self):
		"""
		A template may have a python module with a `get_context` method along with it in the
		same folder. Also the hyphens will be coverted to underscore for python module names.
		This method sets the pymodule_name if it exists.
		"""
		template_basepath = os.path.splitext(self.template_path)[0]
		self.pymodule_name = None

		# replace - with _ in the internal modules names
		self.pymodule_path = os.path.join(
			os.path.dirname(template_basepath),
			os.path.basename(template_basepath.replace("-", "_")) + ".py",
		)

		if os.path.exists(os.path.join(self.app_path, self.pymodule_path)):
			self.pymodule_name = self.app + "." + self.pymodule_path.replace(os.path.sep, ".")[:-3]

	def setup_template_source(self):
		"""Setup template source, frontmatter and markdown conversion"""
		self.original_source = self.source = self.get_raw_template()
		self.extract_frontmatter()
		self.convert_from_markdown()

	def update_context(self):
		self.set_page_properties()
		self.context.build_version = frappe.utils.get_build_version()

		if self.pymodule_name:
			self.pymodule = frappe.get_module(self.pymodule_name)
			self.set_pymodule_properties()

			data = self.run_pymodule_method("get_context")
			# some methods may return a "context" object
			if data:
				self.context.update(data)
			# TODO: self.context.children = self.run_pymodule_method('get_children')

		self.context.developer_mode = frappe.conf.developer_mode
		if self.context.http_status_code:
			self.http_status_code = self.context.http_status_code

	def set_pymodule_properties(self):
		for prop in WEBPAGE_PY_MODULE_PROPERTIES:
			if hasattr(self.pymodule, prop):
				self.context[prop] = getattr(self.pymodule, prop)

	def set_page_properties(self):
		self.context.base_template = self.context.base_template or get_base_template(self.path)
		self.context.basepath = self.basepath
		self.context.basename = self.basename
		self.context.name = self.name
		self.context.path = self.path
		self.context.route = self.path
		self.context.template = self.template_path

	def set_properties_from_source(self):
		if not self.source:
			return
		context = self.context
		if not context.title:
			context.title = extract_title(self.source, self.path)

		base_template = extract_comment_tag(self.source, "base_template")
		if base_template:
			context.base_template = base_template

		if (
			context.base_template
			and "{%- extends" not in self.source
			and "{% extends" not in self.source
			and "</body>" not in self.source
		):
			self.source = f"""{{% extends "{context.base_template}" %}}
				{{% block page_content %}}{self.source}{{% endblock %}}"""

		self.set_properties_via_comments()

	def set_properties_via_comments(self):
		for comment, (context_key, value) in COMMENT_PROPERTY_KEY_VALUE_MAP.items():
			comment_tag = f"<!-- {comment} -->"
			if comment_tag in self.source:
				self.context[context_key] = value
				click.echo(f"\n⚠️  DEPRECATION WARNING: {comment_tag} will be deprecated on 2021-12-31.")
				click.echo(f"Please remove it from {self.template_path} in {self.app}")

	def run_pymodule_method(self, method_name):
		if hasattr(self.pymodule, method_name):
			import inspect

			method = getattr(self.pymodule, method_name)
			if inspect.getfullargspec(method).args:
				return method(self.context)
			else:
				return method()

	def render_template(self):
		if self.template_path.endswith("min.js"):
			html = self.source  # static
		else:
			if self.context.safe_render is not None:
				safe_render = self.context.safe_render
			else:
				safe_render = True

			src_modified = self.source is not self.original_source
			html = frappe.render_template(
				self.source if src_modified else self.context.template, self.context, safe_render=safe_render
			)

		return html

	def extends_template(self):
		return self.template_path.endswith((".html", ".md")) and (
			"{%- extends" in self.source or "{% extends" in self.source
		)

	def get_raw_template(self):
		return frappe.get_jloader().get_source(frappe.get_jenv(), self.context.template)[0]

	def load_colocated_files(self):
		"""load co-located css/js files with the same name"""
		js_path = self.basename + ".js"
		if os.path.exists(js_path) and "{% block script %}" not in self.source:
			self.context.colocated_js = self.get_colocated_file(js_path)

		css_path = self.basename + ".css"
		if os.path.exists(css_path) and "{% block style %}" not in self.source:
			self.context.colocated_css = self.get_colocated_file(css_path)

	def get_colocated_file(self, path):
		with open(path, encoding="utf-8") as f:
			return f.read()

	def extract_frontmatter(self):
		if not self.template_path.endswith((".md", ".html")):
			return

		try:
			# values will be used to update self
			res = get_frontmatter(self.source)
			if res["attributes"]:
				self.context.update(res["attributes"])
				self.source = res["body"]
		except Exception:
			pass

	def convert_from_markdown(self):
		if self.template_path.endswith(".md"):
			self.source = frappe.utils.md_to_html(self.source)
			self.context.page_toc_html = self.source.toc_html

			if not self.context.show_sidebar:
				self.source = '<div class="from-markdown">' + self.source + "</div>"

	def update_toc(self, html):
		if "{index}" in html:
			html = html.replace("{index}", get_toc(self.path))

		if "{next}" in html:
			html = html.replace("{next}", get_next_link(self.path))

		return html

	def set_standard_path(self, path):
		self.app = "frappe"
		self.app_path = frappe.get_app_path("frappe")
		self.path = path
		self.template_path = f"www/{path}.html"

	def set_missing_values(self):
		super().set_missing_values()
		# for backward compatibility
		self.context.docs_base_url = "/docs"

	def set_user_info(self):
		from frappe.utils.user import get_fullname_and_avatar

		info = get_fullname_and_avatar(frappe.session.user)
		self.context["fullname"] = info.fullname
		self.context["user_image"] = info.avatar
		self.context["user"] = info.name


def get_start_folders():
	return frappe.local.flags.web_pages_folders or ("www", "templates/pages")
