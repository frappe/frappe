# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, re, os
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
	template = "templates/generators/web_page.html"
	condition_field = "published"
	page_title_field = "title"
	parent_website_route_field = "parent_web_page"

	def validate(self):
		if self.template_path and not getattr(self, "from_website_sync"):
			frappe.throw(frappe._("Cannot edit templated page"))
		super(WebPage, self).validate()

	def get_context(self, context):
		# if static page, get static content
		if context.slideshow:
			context.update(get_slideshow(self))

		if self.enable_comments:
			context.comment_list = get_comment_list(self.doctype, self.name)

		if self.template_path:
			# render dynamic context (if .py file exists)
			context = self.get_dynamic_context(frappe._dict(context))

			# load content from template
			get_static_content(self, context)
		else:
			context.update({
				"style": self.css or "",
				"script": self.javascript or ""
			})

		self.set_metatags(context)

		if not context.header:
			context.header = self.title

		# for sidebar
		context.children = self.get_children()

		return context

	def render_dynamic(self, context):
		# dynamic
		if context.main_section and ("<!-- render-jinja -->" in context.main_section) \
			or ("{{" in context.main_section):
			try:
				context["main_section"] = render_template(context.main_section,
					context)
				context["no_cache"] = 1
			except TemplateSyntaxError:
				pass

	def get_dynamic_context(self, context):
		template_path_base = self.template_path.rsplit(".", 1)[0]
		template_module = os.path.dirname(os.path.relpath(self.template_path,
			os.path.join(frappe.get_app_path("frappe"),"..", "..")))\
			.replace(os.path.sep, ".") + "." + frappe.scrub(template_path_base.rsplit(os.path.sep, 1)[1])

		try:
			method = template_module.split(".", 1)[1] + ".get_context"
			get_context = frappe.get_attr(method)
			ret = get_context(context)
			if ret:
				context = ret
		except ImportError: pass
		return context

	def set_metatags(self, context):
		context.metatags = {
			"name": context.title,
			"description": context.description or (context.main_section or "")[:150]
		}

		image = find_first_image(context.main_section or "")
		if image:
			context.metatags["image"] = image


def get_static_content(doc, context):
	with open(doc.template_path, "r") as contentfile:
		content = unicode(contentfile.read(), 'utf-8')

		if doc.template_path.endswith(".md"):
			if content:
				lines = content.splitlines()
				first_line = lines[0].strip()

				if first_line.startswith("# "):
					context.title = first_line[2:]
					content = "\n".join(lines[1:])

				content = markdown(content)

		context.main_section = unicode(content.encode("utf-8"), 'utf-8')
		if not context.title:
			context.title = doc.name.replace("-", " ").replace("_", " ").title()

		doc.render_dynamic(context)

	for extn in ("js", "css"):
		fpath = doc.template_path.rsplit(".", 1)[0] + "." + extn
		if os.path.exists(fpath):
			with open(fpath, "r") as f:
				context["css" if extn=="css" else "javascript"] = f.read()

	return context

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
