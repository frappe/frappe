# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

from frappe.utils import get_request_site_address, get_datetime, nowdate
from frappe.website.router import get_pages, get_all_page_context_from_doctypes
from six import iteritems
from six.moves.urllib.parse import quote, urljoin

no_cache = 1
no_sitemap = 1
base_template_path = "templates/www/sitemap.xml"

def get_context(context):
	"""generate the sitemap XML"""
	host = get_request_site_address()
	links = []
	for route, page in iteritems(get_pages()):
		if not page.no_sitemap:
			links.append({
				"loc": urljoin(host, quote(page.name.encode("utf-8"))),
				"lastmod": nowdate()
			})

	for route, data in iteritems(get_all_page_context_from_doctypes()):
		links.append({
			"loc": urljoin(host, quote((route or "").encode("utf-8"))),
			"lastmod": get_datetime(data.get("modified")).strftime("%Y-%m-%d")
		})

	return {"links":links}
