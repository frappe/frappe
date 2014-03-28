# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe, re

from frappe.website.website_generator import WebsiteGenerator
from frappe.website.render import clear_cache
from frappe import _
from frappe.utils import today

class BlogPost(WebsiteGenerator):
	save_versions = True
				
	def get_page_title(self):
		return self.title
		
	def validate(self):
		if not self.blog_intro:
			self.blog_intro = self.content[:140]
			re.sub("\<[^>]*\>", "", self.blog_intro)
		
		if self.blog_intro:
			self.blog_intro = self.blog_intro[:140]
			
		if self.published and not self.published_on:
			self.published_on = today()

		self.parent_website_route = frappe.db.get_value("Website Route",
			{"ref_doctype": "Blog Category", "docname": self.blog_category})

		# update posts
		frappe.db.sql("""update tabBlogger set posts=(select count(*) from `tabBlog Post` 
			where ifnull(blogger,'')=tabBlogger.name)
			where name=%s""", (self.blogger,))
			

	def on_update(self):
		WebsiteGenerator.on_update(self)
		clear_cache("writers")

def clear_blog_cache():
	for blog in frappe.db.sql_list("""select page_name from 
		`tabBlog Post` where ifnull(published,0)=1"""):
		clear_cache(blog)
	
	clear_cache("writers")
