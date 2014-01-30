# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import webnotes
from webnotes.webutils import WebsiteGenerator, cleanup_page_name, delete_page_cache
from webnotes import _
from webnotes.utils import today

class DocType(WebsiteGenerator):
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl

	def autoname(self):
		self.doc.name = cleanup_page_name(self.doc.title)

	def validate(self):
		if self.doc.blog_intro:
			self.doc.blog_intro = self.doc.blog_intro[:140]
			
		if self.doc.published and not self.doc.published_on:
			self.doc.published_on = today()

		# update posts
		webnotes.conn.sql("""update tabBlogger set posts=(select count(*) from `tabBlog Post` 
			where ifnull(blogger,'')=tabBlogger.name)
			where name=%s""", (self.doc.blogger,))

	def on_update(self):
		WebsiteGenerator.on_update(self)
		delete_page_cache("writers")

def clear_blog_cache():
	for blog in webnotes.conn.sql_list("""select page_name from 
		`tabBlog Post` where ifnull(published,0)=1"""):
		delete_page_cache(blog)
	
	delete_page_cache("writers")
