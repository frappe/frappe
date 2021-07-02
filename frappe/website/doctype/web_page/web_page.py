# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import print_function, unicode_literals

import re

import requests
import requests.exceptions
from jinja2.exceptions import TemplateSyntaxError

import frappe
from frappe import _
from frappe.utils import get_datetime, now, strip_html, quoted
from frappe.utils.jinja import render_template
from frappe.website.doctype.website_slideshow.website_slideshow import get_slideshow
from frappe.website.router import resolve_route
from frappe.website.utils import (extract_title, find_first_image, get_comment_list,
	get_html_content_based_on_type)
from frappe.website.website_generator import WebsiteGenerator
from frappe.utils.safe_exec import safe_exec


class WebPage(WebsiteGenerator):
	def validate(self):
		self.validate_dates()
		self.set_route()
		if not self.dynamic_route:
			self.route = quoted(self.route)

	def get_feed(self):
		return self.title

	def on_update(self):
		super(WebPage, self).on_update()

	def on_trash(self):
		super(WebPage, self).on_trash()

	def get_context(self, context):
		context.main_section = get_html_content_based_on_type(self, 'main_section', self.content_type)
		context.source_content_type = self.content_type
		context.title = self.title

		if self.context_script:
			_locals = dict(context = frappe._dict())
			safe_exec(self.context_script, None, _locals)
			context.update(_locals['context'])

		self.render_dynamic(context)

		# if static page, get static content
		if context.slideshow:
			context.update(get_slideshow(self))

		if self.enable_comments:
			context.comment_list = get_comment_list(self.doctype, self.name)
			context.guest_allowed = True

		context.update({
			"style": self.css or "",
			"script": self.javascript or "",
			"header": self.header,
			"text_align": self.text_align,
		})

		if not self.show_title:
			context["no_header"] = 1

		self.set_metatags(context)
		self.set_breadcrumbs(context)
		self.set_title_and_header(context)
		self.set_page_blocks(context)

		return context

	def render_dynamic(self, context):
		# dynamic
		is_jinja = context.dynamic_template or "<!-- jinja -->" in context.main_section
		if is_jinja or ("{{" in context.main_section):
			try:
				context["main_section"] = render_template(context.main_section, context)
				if not "<!-- static -->" in context.main_section:
					context["no_cache"] = 1
			except TemplateSyntaxError:
				if is_jinja:
					raise

	def set_breadcrumbs(self, context):
		"""Build breadcrumbs template """
		if self.breadcrumbs:
			context.parents = frappe.safe_eval(self.breadcrumbs, { "_": _ })
		if not "no_breadcrumbs" in context:
			if "<!-- no-breadcrumbs -->" in context.main_section:
				context.no_breadcrumbs = 1

	def set_title_and_header(self, context):
		"""Extract and set title and header from content or context."""
		if not "no_header" in context:
			if "<!-- no-header -->" in context.main_section:
				context.no_header = 1

		if not context.title:
			context.title = extract_title(context.main_section, context.path_name)

		# header
		if context.no_header and "header" in context:
			context.header = ""

		if not context.no_header:
			# if header not set and no h1 tag in the body, set header as title
			if not context.header and "<h1" not in context.main_section:
				context.header = context.title

			# add h1 tag to header
			if context.get("header") and not re.findall("<h.>", context.header):
				context.header = "<h1>" + context.header + "</h1>"

		# if title not set, set title from header
		if not context.title and context.header:
			context.title = strip_html(context.header)

	def set_page_blocks(self, context):
		if self.content_type != 'Page Builder':
			return
		out = get_web_blocks_html(self.page_blocks)
		context.page_builder_html = out.html
		context.page_builder_scripts = out.scripts
		context.page_builder_styles = out.styles

	def add_hero(self, context):
		"""Add a hero element if specified in content or hooks.
		Hero elements get full page width."""
		context.hero = ""
		if "<!-- start-hero -->" in context.main_section:
			parts1 = context.main_section.split("<!-- start-hero -->")
			parts2 = parts1[1].split("<!-- end-hero -->")
			context.main_section = parts1[0] + parts2[1]
			context.hero = parts2[0]

	def check_for_redirect(self, context):
		if "<!-- redirect:" in context.main_section:
			frappe.local.flags.redirect_location = \
				context.main_section.split("<!-- redirect:")[1].split("-->")[0].strip()
			raise frappe.Redirect

	def set_metatags(self, context):
		if not context.metatags:
			context.metatags = {
				"name": self.meta_title or self.title,
				"description": self.meta_description,
				"image": self.meta_image or find_first_image(context.main_section or ""),
				"og:type": "website"
			}

	def validate_dates(self):
		if self.end_date:
			if self.start_date and get_datetime(self.end_date) < get_datetime(self.start_date):
				frappe.throw(_("End Date cannot be before Start Date!"))

			# If the current date is past end date, and
			# web page is published, empty the end date
			if self.published and now() > self.end_date:
				self.end_date = None

				frappe.msgprint(_("Clearing end date, as it cannot be in the past for published pages."))


def check_publish_status():
	# called via daily scheduler
	web_pages = frappe.get_all("Web Page", fields=["name", "published", "start_date", "end_date"])
	now_date = get_datetime(now())

	for page in web_pages:
		start_date = page.start_date if page.start_date else ""
		end_date = page.end_date if page.end_date else ""

		if page.published:
			# Unpublish pages that are outside the set date ranges
			if (start_date and now_date < start_date) or (end_date and now_date > end_date):
				frappe.db.set_value("Web Page", page.name, "published", 0)
		else:
			# Publish pages that are inside the set date ranges
			if start_date:
				if not end_date or (end_date and now_date < end_date):
					frappe.db.set_value("Web Page", page.name, "published", 1)



def check_broken_links():
	cnt = 0
	for p in frappe.db.sql("select name, main_section from `tabWeb Page`", as_dict=True):
		for link in re.findall('href=["\']([^"\']*)["\']', p.main_section):
			if link.startswith("http"):
				try:
					res = requests.get(link)
				except requests.exceptions.SSLError:
					res = frappe._dict({"status_code": "SSL Error"})
				except requests.exceptions.ConnectionError:
					res = frappe._dict({"status_code": "Connection Error"})

				if res.status_code!=200:
					print("[{0}] {1}: {2}".format(res.status_code, p.name, link))
					cnt += 1
			else:
				link = link[1:] # remove leading /
				link = link.split("#")[0]

				if not resolve_route(link):
					print(p.name + ":" + link)
					cnt += 1

	print("{0} links broken".format(cnt))

def get_web_blocks_html(blocks):
	'''Converts a list of blocks into Raw HTML and extracts out their scripts for deduplication'''

	out = frappe._dict(html='', scripts=[], styles=[])
	extracted_scripts = []
	extracted_styles = []
	for block in blocks:
		web_template = frappe.get_cached_doc('Web Template', block.web_template)
		rendered_html = frappe.render_template('templates/includes/web_block.html', context={
			'web_block': block,
			'web_template_html': web_template.render(block.web_template_values),
			'web_template_type': web_template.type
		})
		html, scripts, styles = extract_script_and_style_tags(rendered_html)
		out.html += html
		if block.web_template not in extracted_scripts:
			out.scripts += scripts
			extracted_scripts.append(block.web_template)
		if block.web_template not in extracted_styles:
			out.styles += styles
			extracted_styles.append(block.web_template)

	return out

def extract_script_and_style_tags(html):
	from bs4 import BeautifulSoup
	soup = BeautifulSoup(html, "html.parser")
	scripts = []
	styles = []

	for script in soup.find_all('script'):
		scripts.append(script.string)
		script.extract()

	for style in soup.find_all('style'):
		styles.append(style.string)
		style.extract()

	return str(soup), scripts, styles
