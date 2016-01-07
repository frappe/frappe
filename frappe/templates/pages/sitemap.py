# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import urllib
import frappe
from frappe.utils import get_request_site_address, get_datetime, nowdate
from frappe.website.router import get_pages, get_generator_routes

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
				"lastmod": nowdate()
			})

	for route, data in get_generator_routes().iteritems():
		links.append({
			"loc": urllib.basejoin(host, urllib.quote((route or "").encode("utf-8"))),
			"lastmod": get_datetime(data.get("modified")).strftime("%Y-%m-%d")
		})

	return {"links":links}
