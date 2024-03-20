# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import re

from jinja2.exceptions import TemplateSyntaxError

import frappe
from frappe import _
from frappe.utils import get_datetime, now, quoted, strip_html
from frappe.utils.caching import redis_cache
from frappe.utils.jinja import render_template
from frappe.utils.safe_exec import safe_exec
from frappe.website.doctype.website_slideshow.website_slideshow import get_slideshow
from frappe.website.utils import (
	extract_title,
	find_first_image,
	get_comment_list,
	get_html_content_based_on_type,
	get_sidebar_items,
)
from frappe.website.website_generator import WebsiteGenerator

H_TAG_PATTERN = re.compile("<h.>")


class WebPage(WebsiteGenerator):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF
		from frappe.website.doctype.web_page_block.web_page_block import WebPageBlock

		breadcrumbs: DF.Code | None
		content_type: DF.Literal["Rich Text", "Markdown", "HTML", "Page Builder", "Slideshow"]
		context_script: DF.Code | None
		css: DF.Code | None
		dynamic_route: DF.Check
		dynamic_template: DF.Check
		enable_comments: DF.Check
		end_date: DF.Datetime | None
		full_width: DF.Check
		header: DF.HTMLEditor | None
		idx: DF.Int
		insert_style: DF.Check
		javascript: DF.Code | None
		main_section: DF.TextEditor | None
		main_section_html: DF.HTMLEditor | None
		main_section_md: DF.MarkdownEditor | None
		meta_description: DF.SmallText | None
		meta_image: DF.AttachImage | None
		meta_title: DF.Data | None
		module: DF.Link | None
		page_blocks: DF.Table[WebPageBlock]
		published: DF.Check
		route: DF.Data | None
		show_sidebar: DF.Check
		show_title: DF.Check
		slideshow: DF.Link | None
		start_date: DF.Datetime | None
		text_align: DF.Literal["Left", "Center", "Right"]
		title: DF.Data
		website_sidebar: DF.Link | None
	# end: auto-generated types

	def validate(self):
		self.validate_dates()
		self.set_route()
		if not self.dynamic_route:
			self.route = quoted(self.route)

	def get_context(self, context):
		context.main_section = get_html_content_based_on_type(self, "main_section", self.content_type)
		context.source_content_type = self.content_type
		context.title = self.title

		if self.context_script:
			_locals = dict(context=frappe._dict())
			safe_exec(self.context_script, None, _locals, script_filename=f"web page {self.name}")
			context.update(_locals["context"])

		self.render_dynamic(context)

		# if static page, get static content
		if context.slideshow:
			context.update(get_slideshow(self))

		if self.enable_comments:
			context.comment_list = get_comment_list(self.doctype, self.name)
			context.guest_allowed = True

		context.update(
			{
				"style": self.css or "",
				"script": self.javascript or "",
				"header": self.header,
				"text_align": self.text_align,
			}
		)

		if not self.show_title:
			context["no_header"] = 1

		if self.show_sidebar:
			context.sidebar_items = get_sidebar_items(self.website_sidebar)

		self.set_metatags(context)
		self.set_breadcrumbs(context)
		self.set_title_and_header(context)
		self.set_page_blocks(context)

		return context

	def render_dynamic(self, context):
		# dynamic
		is_jinja = (
			context.dynamic_template
			or "<!-- jinja -->" in context.main_section
			or ("{{" in context.main_section)
		)
		if is_jinja:
			frappe.flags.web_block_scripts = {}
			frappe.flags.web_block_styles = {}
			try:
				context["main_section"] = render_template(context.main_section, context)
				if "<!-- static -->" not in context.main_section:
					context["no_cache"] = 1
			except TemplateSyntaxError:
				raise
			finally:
				frappe.flags.web_block_scripts = {}
				frappe.flags.web_block_styles = {}

	def set_breadcrumbs(self, context):
		"""Build breadcrumbs template"""
		if self.breadcrumbs:
			context.parents = frappe.safe_eval(self.breadcrumbs, {"_": _})
		if "no_breadcrumbs" not in context:
			if "<!-- no-breadcrumbs -->" in context.main_section:
				context.no_breadcrumbs = 1

	def set_title_and_header(self, context):
		"""Extract and set title and header from content or context."""
		if "no_header" not in context:
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
			if context.get("header") and not H_TAG_PATTERN.findall(context.header):
				context.header = "<h1>" + context.header + "</h1>"

		# if title not set, set title from header
		if not context.title and context.header:
			context.title = strip_html(context.header)

	def set_page_blocks(self, context):
		if self.content_type != "Page Builder":
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
			frappe.local.flags.redirect_location = (
				context.main_section.split("<!-- redirect:", 2)[1].split("-->", 1)[0].strip()
			)
			raise frappe.Redirect

	def set_metatags(self, context):
		if not context.metatags:
			context.metatags = {
				"name": self.meta_title or self.title,
				"description": self.meta_description,
				"image": self.meta_image or find_first_image(context.main_section or ""),
				"og:type": "website",
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


def get_web_blocks_html(blocks):
	"""Convert a list of blocks into Raw HTML and extract out their scripts for deduplication."""

	out = frappe._dict(html="", scripts={}, styles={})
	extracted_scripts = {}
	extracted_styles = {}
	for block in blocks:
		web_template = frappe.get_cached_doc("Web Template", block.web_template)
		rendered_html = frappe.render_template(
			"templates/includes/web_block.html",
			context={
				"web_block": block,
				"web_template_html": web_template.render(block.web_template_values),
				"web_template_type": web_template.type,
			},
		)
		html, scripts, styles = extract_script_and_style_tags(rendered_html)
		out.html += html
		if block.web_template not in extracted_scripts:
			extracted_scripts.setdefault(block.web_template, [])
			extracted_scripts[block.web_template] += scripts

		if block.web_template not in extracted_styles:
			extracted_styles.setdefault(block.web_template, [])
			extracted_styles[block.web_template] += styles

	out.scripts = extracted_scripts
	out.styles = extracted_styles

	return out


def extract_script_and_style_tags(html):
	from bs4 import BeautifulSoup

	soup = BeautifulSoup(html, "html.parser")
	scripts = []
	styles = []

	for script in soup.find_all("script"):
		scripts.append(script.string)
		script.extract()

	for style in soup.find_all("style"):
		styles.append(style.string)
		style.extract()

	return str(soup), scripts, styles


@redis_cache(ttl=60 * 60)
def get_dynamic_web_pages() -> dict[str, str]:
	pages = frappe.get_all(
		"Web Page",
		fields=["name", "route", "modified"],
		filters=dict(published=1, dynamic_route=1),
		update={"doctype": "Web Page"},
	)
	get_web_pages_with_dynamic_routes = frappe.get_hooks("get_web_pages_with_dynamic_routes") or []
	for method in get_web_pages_with_dynamic_routes:
		pages.extend(frappe.get_attr(method)())
	return pages
