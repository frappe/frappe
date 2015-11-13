# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, re, os, json, imp
import requests, requests.exceptions
from frappe.website.website_generator import WebsiteGenerator
from frappe.website.router import resolve_route
from frappe.website.doctype.website_slideshow.website_slideshow import get_slideshow
from frappe.website.utils import find_first_image, get_comment_list
from markdown2 import markdown
from frappe.utils.jinja import render_template
from jinja2.exceptions import TemplateSyntaxError

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
		if self.template_path and not getattr(self, "from_website_sync"):
			frappe.throw(frappe._("Cannot edit templated page"))

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

		if self.template_path:
			# render dynamic context (if .py file exists)

			# get absolute template path considering first fragment as app name
			split_path = self.template_path.split(os.sep)
			self.template_path = os.path.join(frappe.get_app_path(split_path[0]), *split_path[1:])

			context = self.get_dynamic_context(frappe._dict(context))

			# load content from template
			self.get_static_content(context)
		else:
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

	def get_static_content(self, context):

		with open(self.template_path, "r") as contentfile:
			content = unicode(contentfile.read(), 'utf-8')

			if self.template_path.endswith(".md"):
				if content:
					lines = content.splitlines()
					first_line = lines[0].strip()

					if first_line.startswith("# "):
						context.title = first_line[2:]
						content = "\n".join(lines[1:])

					content = markdown(content)

			context.main_section = unicode(content.encode("utf-8"), 'utf-8')

			self.check_for_redirect(context)

			if not context.title:
				context.title = self.name.replace("-", " ").replace("_", " ").title()

			self.render_dynamic(context)

		for extn in ("js", "css"):
			fpath = self.template_path.rsplit(".", 1)[0] + "." + extn
			if os.path.exists(fpath):
				with open(fpath, "r") as f:
					context["style" if extn=="css" else "script"] = f.read()

	def check_for_redirect(self, context):
		if "<!-- redirect:" in context.main_section:
			frappe.local.flags.redirect_location = \
				context.main_section.split("<!-- redirect:")[1].split("-->")[0].strip()
			raise frappe.Redirect

	def get_dynamic_context(self, context):
		"update context from `.py` and load sidebar from `_sidebar.json` if either exists"
		basename = os.path.basename(self.template_path).rsplit(".", 1)[0]
		module_path = os.path.join(os.path.dirname(self.template_path),
			frappe.scrub(basename) + ".py")

		if os.path.exists(module_path):
			module = imp.load_source(basename, module_path)
			if hasattr(module, "get_context"):
				ret = module.get_context(context)
				if ret:
					context = ret

		# sidebar?
		sidebar_path = os.path.join(os.path.dirname(self.template_path), "_sidebar.json")
		if os.path.exists(sidebar_path):
			with open(sidebar_path, "r") as f:
				context.children = json.loads(f.read())

		return context

	def set_metatags(self, context):
		context.metatags = {
			"name": context.title,
			"description": (context.description or context.main_section or "").replace("\n", " ")[:500]
		}

		image = find_first_image(context.main_section or "")
		if image:
			context.metatags["image"] = image

# def get_list_context(context=None):
# 	list_context = frappe._dict(
# 		title = _("Website Search"),
# 		template = "templates/includes/kb_list.html",
# 		row_template = "templates/includes/kb_row.html",
# 		get_level_class = get_level_class,
# 		hide_filters = True,
# 		filters = {"published": 1}
# 	)
#
# 	if frappe.local.form_dict.txt:
# 		list_context.subtitle = _('Filtered by "{0}"').format(frappe.local.form_dict.txt)
# 	#
# 	# list_context.update(frappe.get_doc("Blog Settings", "Blog Settings").as_dict())
# 	return list_context

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
