# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals
import webnotes

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
def add_to_sitemap(options):
	doc = webnotes.doc({"doctype":"Website Sitemap"})
	for key in ("page_name", "docname", "page_or_generator", "lastmod"):
		doc.fields[key] = options.get(key)
	if not doc.page_name:
		doc.page_name = options.link_name
	doc.name = doc.page_name
	doc.website_sitemap_config = options.link_name
	doc.insert()
