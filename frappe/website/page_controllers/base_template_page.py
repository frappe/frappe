import os

import frappe
from frappe import _
from frappe.website.doctype.website_settings.website_settings import \
	get_website_settings
from frappe.website.page_controllers.web_page import WebPage


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
