# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from urllib.parse import quote, urljoin

import frappe
from frappe.utils import cstr, escape_html, get_request_site_address, now

no_cache = 1
base_template_path = "www/rss.xml"


def get_context(context):
	"""generate rss feed"""

	host = get_request_site_address()

	blog_list = frappe.get_all(
		"Blog Post",
		fields=["name", "published_on", "modified", "title", "blog_intro", "route"],
		filters={"published": 1},
		order_by="published_on desc",
		limit=20,
	)

	for blog in blog_list:
		blog.link = urljoin(host, blog.route)
		blog.blog_intro = escape_html(blog.blog_intro or "")
		blog.title = escape_html(blog.title or "")

	if blog_list:
		modified = max(blog["modified"] for blog in blog_list)
	else:
		modified = now()

	blog_settings = frappe.get_doc("Blog Settings", "Blog Settings")

	context = {
		"title": blog_settings.blog_title or "Blog",
		"description": blog_settings.blog_introduction or "",
		"modified": modified,
		"items": blog_list,
		"link": host + "/blog",
	}

	# print context
	return context
