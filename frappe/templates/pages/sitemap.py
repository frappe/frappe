# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals

import urllib
import frappe
from frappe.utils import get_request_site_address

no_cache = 1
no_sitemap = 1
base_template_path = "templates/pages/sitemap.xml"

def get_context(context):
	"""generate the sitemap XML"""
	host = get_request_site_address()
	links = []
	for l in frappe.db.sql("""select `tabWebsite Route`.page_name, `tabWebsite Route`.lastmod 
		from `tabWebsite Route`, `tabWebsite Template` 
		where 
			`tabWebsite Route`.website_template = `tabWebsite Template`.name
			and ifnull(`tabWebsite Template`.no_sitemap, 0)=0""", 
		as_dict=True):
		links.append({
			"loc": urllib.basejoin(host, urllib.quote(l.page_name.encode("utf-8"))),
			"lastmod": l.lastmod
		})
	
	return {"links":links}
	