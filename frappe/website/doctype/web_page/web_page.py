# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, re
import requests, requests.exceptions
from frappe.website.website_generator import WebsiteGenerator
from frappe.website.doctype.website_slideshow.website_slideshow import get_slideshow
from frappe.website.utils import find_first_image, get_comment_list

template = "templates/generators/web_page.html"
condition_field = "published"

class WebPage(WebsiteGenerator):
	save_versions = True
	def get_context(self, context):
		# if static page, get static content
		if context.slideshow:
			context.update(get_slideshow(self))

		if self.enable_comments:
			context.comment_list = get_comment_list(self.doctype, self.name)

		context.update({
			"style": self.css or "",
			"script": self.javascript or ""
		})

		if "<!-- render-jinja -->" in self.main_section:
			context["main_section"] = frappe.render_template(self.main_section,
				{"doc": self, "frappe": frappe})
			context["no_cache"] = 1

		context.metatags = {
			"name": self.title,
			"description": self.description or (self.main_section or "")[:150]
		}

		image = find_first_image(self.main_section or "")
		if image:
			context.metatags["image"] = image

		if not context.header:
			context.header = self.title

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

				if not frappe.db.exists("Website Route", link):
					print p.name + ":" + link
					cnt += 1

	print "{0} links broken".format(cnt)
