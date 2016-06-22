# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, re
import requests, requests.exceptions
from frappe.utils import strip_html
from frappe.website.website_generator import WebsiteGenerator
from frappe.website.router import resolve_route
from frappe.website.doctype.website_slideshow.website_slideshow import get_slideshow
from frappe.website.utils import find_first_image, get_comment_list, get_full_index
from frappe.utils.jinja import render_template
from jinja2.exceptions import TemplateSyntaxError
from frappe import _

class WebPage(WebsiteGenerator):
	save_versions = True
	website = frappe._dict(
		template = "templates/generators/web_page.html",
		condition_field = "published",
		page_title_field = "title",
		parent_website_route_field = "parent_web_page"
	)

	def get_feed(self):
		return self.title

	def validate(self):
		# avoid recursive parent_web_page.
		if self.parent_web_page == self.page_name:
			self.parent_web_page = ""
			self.parent_website_route = ""

		super(WebPage, self).validate()

	def get_context(self, context):
		# if static page, get static content
		if context.slideshow:
			context.update(get_slideshow(self))

		if self.enable_comments:
			context.comment_list = get_comment_list(self.doctype, self.name)

		# for sidebar and breadcrumbs
		context.children = self.get_children()
		context.parents = self.get_parents(context)

		context.update({
			"style": self.css or "",
			"script": self.javascript or "",
			"header": self.header,
			"title": self.title,
			"text_align": self.text_align,
		})

		if self.description:
			context.setdefault("metatags", {})["description"] = self.description

		if not self.show_title:
			context["no_header"] = 1

		self.set_metatags(context)
		self.set_breadcrumbs(context)
		self.set_title_and_header(context)
		self.add_index(context)

		return context

	def render_dynamic(self, context):
		# dynamic
		is_jinja = "<!-- jinja -->" in context.main_section
		if is_jinja or ("{{" in context.main_section):
			try:
				context["main_section"] = render_template(context.main_section,
					context)
				if not "<!-- static -->" in context.main_section:
					context["no_cache"] = 1
			except TemplateSyntaxError:
				if is_jinja:
					raise

	def set_breadcrumbs(self, context):
		"""Build breadcrumbs template (deprecated)"""
		if not "no_breadcrumbs" in context:
			if "<!-- no-breadcrumbs -->" in context.main_section:
				context.no_breadcrumbs = 1

	def set_title_and_header(self, context):
		"""Extract and set title and header from content or context."""
		if not "no_header" in context:
			if "<!-- no-header -->" in context.main_section:
				context.no_header = 1

		if "<!-- title:" in context.main_section:
			context.title = re.findall('<!-- title:([^>]*) -->', context.main_section)[0].strip()

		if context.get("page_titles") and context.page_titles.get(context.pathname):
			context.title = context.page_titles.get(context.pathname)[0]

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

	def add_index(self, context):
		"""Add index, next button if `{index}`, `{next}` is present."""
		# table of contents

		extn = ""
		if context.page_links_with_extn:
			extn = ".html"

		if "{index}" in context.main_section and context.get("children") and len(context.children):
			full_index = get_full_index(context.pathname, extn = extn)

			if full_index:
				html = frappe.get_template("templates/includes/full_index.html").render({
					"full_index": full_index,
					"url_prefix": context.url_prefix
				})

				context.main_section = context.main_section.replace("{index}", html)

		# next and previous
		if "{next}" in context.main_section:
			next_item = self.get_next()
			next_item.extn = "" if self.has_children(next_item.name) else extn
			if next_item and next_item.page_name:
				if context.relative_links:
					if next_item.next_parent:
						next_item.name = "../" + next_item.page_name or ""
					else:
						next_item.name = next_item.page_name or ""
				else:
					if next_item and next_item.name and next_item.name[0]!="/":
						next_item.name = "/" + next_item.name

				if not next_item.title:
					next_item.title = ""
				html = ('<p class="btn-next-wrapper">'+_("Next")\
					+': <a class="btn-next" href="{name}{extn}">{title}</a></p>').format(**next_item)
			else:
				html = ""

			context.main_section = context.main_section.replace("{next}", html)

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
		context.metatags = {
			"name": context.title,
			"description": (context.description or "").replace("\n", " ")[:500]
		}

		image = find_first_image(context.main_section or "")
		if image:
			context.metatags["image"] = image

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
					print "[{0}] {1}: {2}".format(res.status_code, p.name, link)
					cnt += 1
			else:
				link = link[1:] # remove leading /
				link = link.split("#")[0]

				if not resolve_route(link):
					print p.name + ":" + link
					cnt += 1

	print "{0} links broken".format(cnt)
