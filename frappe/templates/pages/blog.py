# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, re
from frappe import _
from frappe.utils import global_date_format

page_title = "Blog"
def get_context(context):
	context.update(frappe.get_doc("Blog Settings", "Blog Settings").as_dict())
	context.children = get_children()
	context.posts = get_blog_list(category=context.category, by=frappe.form_dict.by)

def get_children(context=None):
	return frappe.db.sql("""select concat("blog/", page_name) as name,
		title from `tabBlog Category`
		where ifnull(published, 0) = 1 order by title asc""", as_dict=1)

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

	posts = frappe.db.sql(query, as_dict=1)

	for post in posts:
		post.published = global_date_format(post.creation)
		post.content = re.sub('\<[^>]*\>', '', post.content[:140])
		if not post.comments:
			post.comment_text = _('No comments yet')
		elif post.comments==1:
			post.comment_text = _('1 comment')
		else:
			post.comment_text = _('{0} comments').format(str(post.comments))

		post.avatar = post.avatar or ""

		if (not "http:" in post.avatar or "https:" in post.avatar) and not post.avatar.startswith("/"):
			post.avatar = "/" + post.avatar

		post.month = post.month.upper()[:3]

	return frappe.render_template("templates/includes/blog_list.html", {"posts": posts})
