# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe, re

from frappe.website.website_generator import WebsiteGenerator
from frappe.website.render import clear_cache
from frappe.utils import today, cint, global_date_format, get_fullname
from frappe.website.utils import find_first_image, get_comment_list
from frappe.templates.pages.blog import get_children

class BlogPost(WebsiteGenerator):
	condition_field = "published"
	template = "templates/generators/blog_post.html"
	save_versions = True
	order_by = "published_on desc"
	parent_website_route_field = "blog_category"
	page_title_field = "title"

	def validate(self):
		super(BlogPost, self).validate()

		if not self.blog_intro:
			self.blog_intro = self.content[:140]
			self.blog_intro = re.sub("\<[^>]*\>", "", self.blog_intro)

		if self.blog_intro:
			self.blog_intro = self.blog_intro[:140]

		if self.published and not self.published_on:
			self.published_on = today()

		# update posts
		frappe.db.sql("""update tabBlogger set posts=(select count(*) from `tabBlog Post`
			where ifnull(blogger,'')=tabBlogger.name)
			where name=%s""", (self.blogger,))

	def on_update(self):
		WebsiteGenerator.on_update(self)
		clear_cache("writers")

	def get_context(self, context):
		# this is for double precaution. usually it wont reach this code if not published
		if not cint(self.published):
			raise Exception, "This blog has not been published yet!"

		# temp fields
		context.full_name = get_fullname(self.owner)
		context.updated = global_date_format(self.published_on)

		if self.blogger:
			context.blogger_info = frappe.get_doc("Blogger", self.blogger).as_dict()

		context.description = self.blog_intro or self.content[:140]

		context.metatags = {
			"name": self.title,
			"description": context.description,
		}

		image = find_first_image(self.content)
		if image:
			context.metatags["image"] = image

		context.categories = frappe.db.sql_list("""select name from
			`tabBlog Category` order by name""")

		context.comment_list = get_comment_list(self.doctype, self.name)

		context.children = get_children()

		return context

def clear_blog_cache():
	for blog in frappe.db.sql_list("""select page_name from
		`tabBlog Post` where ifnull(published,0)=1"""):
		clear_cache(blog)

	clear_cache("writers")

@frappe.whitelist(allow_guest=True)
def get_blog_list(start=0, by=None, category=None):
	condition = ""
	if by:
		condition = " and t1.blogger='%s'" % by.replace("'", "\'")
	if category:
		condition += " and t1.blog_category='%s'" % category.replace("'", "\'")
	query = """\
		select
			t1.title, t1.name,
				concat(t1.parent_website_route, "/", t1.page_name) as page_name,
				t1.published_on as creation,
				day(t1.published_on) as day, monthname(t1.published_on) as month,
				year(t1.published_on) as year,
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

	result = frappe.db.sql(query, as_dict=1)

	# strip html tags from content
	for res in result:
		res['published'] = global_date_format(res['creation'])
		res['content'] = res['content'][:140]

	return result

