# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import print_function, unicode_literals

import re

import requests
import requests.exceptions
from jinja2.exceptions import TemplateSyntaxError

import frappe
from frappe import _
from frappe.utils import get_datetime, now, strip_html
from frappe.utils.jinja import render_template
from frappe.website.doctype.website_slideshow.website_slideshow import get_slideshow
from frappe.website.router import resolve_route
from frappe.website.utils import (extract_title, find_first_image, get_comment_list,
	get_html_content_based_on_type)
from frappe.website.website_generator import WebsiteGenerator


class WebPage(WebsiteGenerator):
	def validate(self):
		self.validate_dates()
		self.set_route()

	def get_feed(self):
		return self.title

	def get_context(self, context):
		context.main_section = get_html_content_based_on_type(self, 'main_section', self.content_type)

		# if static page, get static content
		if context.slideshow:
			context.update(get_slideshow(self))

		if self.enable_comments:
			context.comment_list = get_comment_list(self.doctype, self.name)

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
