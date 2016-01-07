# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.website.website_generator import WebsiteGenerator
from frappe.website.render import clear_cache
from frappe.utils import today, cint, global_date_format, get_fullname, strip_html_tags
from frappe.website.utils import find_first_image, get_comment_list
from markdown2 import markdown

class BlogPost(WebsiteGenerator):
	save_versions = True
	website = frappe._dict(
		condition_field = "published",
		template = "templates/generators/blog_post.html",
		order_by = "published_on desc",
		parent_website_route_field = "blog_category",
		page_title_field = "title"
	)

	def get_feed(self):
		return self.title

	def validate(self):
		super(BlogPost, self).validate()

		if not self.blog_intro:
			self.blog_intro = self.content[:140]
			self.blog_intro = strip_html_tags(self.blog_intro)

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

		if "<!-- markdown -->" in context.content:
			context.content = markdown(context.content)

		image = find_first_image(self.content)
		if image:
			context.metatags["image"] = image

		context.comment_list = get_comment_list(self.doctype, self.name)

		context.children = get_children()

		category = frappe.db.get_value("Blog Category", context.doc.blog_category, ["title", "page_name"], as_dict=1)
		context.parents = [{"title": category.title, "name": "blog/{0}".format(category.page_name)}]

def get_list_context(context=None):
	list_context = frappe._dict(
		page_title = _("Blog"),
		template = "templates/includes/blog/blog.html",
		row_template = "templates/includes/blog/blog_row.html",
		get_list = get_blog_list,
		hide_filters = True,
		children = get_children()
	)

	if frappe.local.form_dict.category:
		list_context.blog_subtitle = _("Posts filed under {0}").format(get_blog_category(frappe.local.form_dict.category))

	elif frappe.local.form_dict.by:
		blogger = frappe.db.get_value("Blogger", {"name": frappe.local.form_dict.by}, "full_name")
		list_context.blog_subtitle = _("Posts by {0}").format(blogger)

	elif frappe.local.form_dict.txt:
		list_context.blog_subtitle = _('Filtered by "{0}"').format(frappe.local.form_dict.txt)

	list_context.update(frappe.get_doc("Blog Settings", "Blog Settings").as_dict(no_default_fields=True))
	return list_context

def get_children():
	return frappe.db.sql("""select concat("blog/", page_name) as name,
		title from `tabBlog Category`
		where published = 1
		and exists (select name from `tabBlog Post`
			where `tabBlog Post`.blog_category=`tabBlog Category`.name and published=1)
		order by title asc""", as_dict=1)

def clear_blog_cache():
	for blog in frappe.db.sql_list("""select page_name from
		`tabBlog Post` where ifnull(published,0)=1"""):
		clear_cache(blog)

	clear_cache("writers")

def get_blog_category(page_name):
	return frappe.db.get_value("Blog Category", {"page_name": page_name }) or page_name

def get_blog_list(doctype, txt=None, filters=None, limit_start=0, limit_page_length=20):
	conditions = []
	if filters:
		if filters.by:
			conditions.append('t1.blogger="%s"' % frappe.db.escape(filters.by))
		if filters.category:
			conditions.append('t1.blog_category="%s"' % frappe.db.escape(get_blog_category(filters.category)))

	if txt:
		conditions.append('t1.content like "%{0}%"'.format(frappe.db.escape(txt)))

	if conditions:
		frappe.local.no_cache = 1

	query = """\
		select
			t1.title, t1.name, t1.blog_category, t1.parent_website_route, t1.published_on,
				concat(t1.parent_website_route, "/", t1.page_name) as page_name,
				t1.published_on as creation,
				ifnull(t1.blog_intro, t1.content) as content,
				t2.full_name, t2.avatar, t1.blogger,
				(select count(name) from `tabComment` where
					comment_doctype='Blog Post' and comment_docname=t1.name and comment_type="Comment") as comments
		from `tabBlog Post` t1, `tabBlogger` t2
		where ifnull(t1.published,0)=1
		and t1.blogger = t2.name
		%(condition)s
		order by published_on desc, name asc
		limit %(start)s, %(page_len)s""" % {
			"start": limit_start, "page_len": limit_page_length,
				"condition": (" and " + " and ".join(conditions)) if conditions else ""
		}

	posts = frappe.db.sql(query, as_dict=1)

	for post in posts:
		post.published = global_date_format(post.creation)
		post.content = strip_html_tags(post.content[:140])
		if not post.comments:
			post.comment_text = _('No comments yet')
		elif post.comments==1:
			post.comment_text = _('1 comment')
		else:
			post.comment_text = _('{0} comments').format(str(post.comments))

		post.avatar = post.avatar or ""

		if (not "http:" in post.avatar or "https:" in post.avatar) and not post.avatar.startswith("/"):
			post.avatar = "/" + post.avatar

	return posts
