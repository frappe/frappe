# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import markdown2
import webnotes
from webnotes.utils import global_date_format, get_fullname, cint

doctype = "Blog Post"
condition_field = "published"

def get_context(context):
	blog_post = context.bean.doc
	
	# this is for double precaution. usually it wont reach this code if not published
	if not cint(blog_post.published):
		raise Exception, "This blog has not been published yet!"
	
	# temp fields
	blog_post.full_name = get_fullname(blog_post.owner)
	blog_post.updated = global_date_format(blog_post.published_on)
	
	if blog_post.blogger:
		blog_post.blogger_info = webnotes.doc("Blogger", blog_post.blogger).fields
	
	blog_post.description = blog_post.blog_intro or blog_post.content[:140]
	blog_post.meta_description = blog_post.description
	
	blog_post.categories = webnotes.conn.sql_list("select name from `tabBlog Category` order by name")
	
	blog_post.comment_list = webnotes.conn.sql("""\
		select comment, comment_by_fullname, creation
		from `tabComment` where comment_doctype="Blog Post"
		and comment_docname=%s order by creation""", (blog_post.name,), as_dict=1) or []
	
	
	return blog_post.fields
	
@webnotes.whitelist(allow_guest=True)
def get_blog_list(start=0, by=None, category=None):
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
	for res in result:
		res['published'] = global_date_format(res['creation'])
		if not res['content']:
			res['content'] = webnotes.webutils.get_html(res['page_name'])
		res['content'] = res['content'][:140]
		
	return result
