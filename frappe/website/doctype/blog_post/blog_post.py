# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe

from frappe.website.website_generator import WebsiteGenerator
from frappe.website.render import clear_cache
from frappe import _
from frappe.utils import today

class DocType(WebsiteGenerator):
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def get_page_title(self):
		return self.doc.title
		
	def get_parent_website_sitemap(self):
		return frappe.conn.get_value("Website Sitemap", {"ref_doctype": "Blog Category", "docname": self.doc.blog_category})

	def validate(self):
		if self.doc.blog_intro:
			self.doc.blog_intro = self.doc.blog_intro[:140]
			
		if self.doc.published and not self.doc.published_on:
			self.doc.published_on = today()

		# update posts
		frappe.conn.sql("""update tabBlogger set posts=(select count(*) from `tabBlog Post` 
			where ifnull(blogger,'')=tabBlogger.name)
			where name=%s""", (self.doc.blogger,))

	def on_update(self):
		WebsiteGenerator.on_update(self)
		clear_cache("writers")

def clear_blog_cache():
	for blog in frappe.conn.sql_list("""select page_name from 
		`tabBlog Post` where ifnull(published,0)=1"""):
		clear_cache(blog)
	
	clear_cache("writers")
