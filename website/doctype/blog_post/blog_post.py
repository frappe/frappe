# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import webnotes
import webnotes.webutils
from webnotes.webutils import WebsiteGenerator, cleanup_page_name
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
			where name=%s""", self.doc.blogger)

	def on_update(self):
		WebsiteGenerator.on_update(self)
		webnotes.webutils.delete_page_cache("writers")

	def get_context(self):
		import webnotes.utils
		import markdown2
		
		# this is for double precaution. usually it wont reach this code if not published
		if not webnotes.utils.cint(self.doc.published):
			raise Exception, "This blog has not been published yet!"
		
		# temp fields
		from webnotes.utils import global_date_format, get_fullname
		self.doc.full_name = get_fullname(self.doc.owner)
		self.doc.updated = global_date_format(self.doc.published_on)
		
		if self.doc.blogger:
			self.doc.blogger_info = webnotes.doc("Blogger", self.doc.blogger).fields
		
		self.doc.description = self.doc.blog_intro or self.doc.content[:140]
		self.doc.meta_description = self.doc.description
		
		self.doc.categories = webnotes.conn.sql_list("select name from `tabBlog Category` order by name")
		
		self.doc.comment_list = webnotes.conn.sql("""\
			select comment, comment_by_fullname, creation
			from `tabComment` where comment_doctype="Blog Post"
			and comment_docname=%s order by creation""", self.doc.name, as_dict=1) or []
						
			
def clear_blog_cache():
	for blog in webnotes.conn.sql_list("""select page_name from 
		`tabBlog Post` where ifnull(published,0)=1"""):
		webnotes.webutils.delete_page_cache(blog)
	
	webnotes.webutils.delete_page_cache("writers")

@webnotes.whitelist(allow_guest=True)
def get_blog_list(start=0, by=None, category=None):
	import webnotes
	condition = ""
	if by:
		condition = " and t1.blogger='%s'" % by.replace("'", "\'")
	if category:
		condition += " and t1.blog_category='%s'" % category.replace("'", "\'")
	query = """\
		select
			t1.title, t1.name, t1.page_name, t1.published_on as creation, 
				ifnull(t1.blog_intro, t1.content) as content, 
				t2.full_name, t2.avatar, t1.blogger,
				(select count(name) from `tabComment` where
					comment_doctype='Blog Post' and comment_docname=t1.name) as comments
		from `tabBlog Post` t1, `tabBlogger` t2
		where ifnull(t1.published,0)=1
		and t1.blogger = t2.name
		%(condition)s
		order by published_on desc, name asc
		limit %(start)s, 20""" % {"start": start, "condition": condition}
		
	result = webnotes.conn.sql(query, as_dict=1)

	# strip html tags from content
	import webnotes.utils
	
	for res in result:
		from webnotes.utils import global_date_format
		res['published'] = global_date_format(res['creation'])
		if not res['content']:
			res['content'] = webnotes.webutils.get_html(res['page_name'])
		res['content'] = res['content'][:140]
		
	return result
