# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import urllib
import frappe
from frappe.utils import get_request_site_address, get_datetime
from frappe.website.router import get_pages, process_generators

no_cache = 1
no_sitemap = 1
base_template_path = "templates/pages/sitemap.xml"

def get_context(context):
	"""generate the sitemap XML"""
	host = get_request_site_address()
	links = []
	for page in get_pages():
		if not page.no_sitemap:
			links.append({
				"loc": urllib.basejoin(host, urllib.quote(page.name.encode("utf-8"))),
				"lastmod": "2014-01-01"
			})

	def add_links(doctype, condition_field, order_by):
		meta = frappe.get_meta(doctype)
		page_name = "page_name"
		condition = ""

		if meta.get_field("parent_website_route"):
			page_name = """concat(ifnull(parent_website_route, ""),
				if(ifnull(parent_website_route, "")="", "", "/"), page_name)"""
		if condition_field:
			condition ="where ifnull({0}, 0)=1".format(condition_field)

		for route in frappe.db.sql("select {0}, modified from `tab{1}` {2}".format(page_name,
			doctype, condition)):
			if route[0]:
				links.append({
					"loc": urllib.basejoin(host, urllib.quote(route[0].encode("utf-8"))),
					"lastmod": get_datetime(route[1]).strftime("%Y-%m-%d")
				})

	process_generators(add_links)

	return {"links":links}
