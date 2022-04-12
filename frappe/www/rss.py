# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

from six.moves.urllib.parse import quote, urljoin

import frappe
from frappe.utils import cstr, escape_html, get_request_site_address, now

no_cache = 1
base_template_path = "templates/www/rss.xml"


def get_context(context):
	"""generate rss feed"""

	host = get_request_site_address()

	blog_list = frappe.db.sql(
		"""\
		select route as name, published_on, modified, title, content from `tabBlog Post`
		where ifnull(published,0)=1
		order by published_on desc limit 20""",
		as_dict=1,
	)

	for blog in blog_list:
		blog_page = cstr(quote(blog.name.encode("utf-8")))
		blog.link = urljoin(host, blog_page)
		blog.content = escape_html(blog.content or "")

	if blog_list:
		modified = max((blog["modified"] for blog in blog_list))
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
