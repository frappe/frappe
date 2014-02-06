# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import webnotes

def execute():
	webnotes.reload_doc("website", "doctype", "website_sitemap")
	webnotes.reload_doc("website", "doctype", "website_sitemap_permission")
	webnotes.reload_doc("website", "doctype", "website_group")
	webnotes.reload_doc("website", "doctype", "post")
	webnotes.reload_doc("website", "doctype", "user_vote")
	
	webnotes.conn.sql("""update `tabWebsite Sitemap` ws set ref_doctype=(select wsc.ref_doctype
		from `tabWebsite Sitemap Config` wsc where wsc.name=ws.website_sitemap_config)
		where ifnull(page_or_generator, '')!='Page'""")
	
	home_page = webnotes.conn.get_value("Website Settings", "Website Settings", "home_page")
	home_page = webnotes.conn.get_value("Website Sitemap", {"docname": home_page}) or home_page
	webnotes.conn.set_value("Website Settings", "Website Settings", "home_page",
		home_page)
