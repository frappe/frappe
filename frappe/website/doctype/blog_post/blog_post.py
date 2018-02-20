# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.website.website_generator import WebsiteGenerator
from frappe.website.render import clear_cache
from frappe.utils import today, cint, global_date_format, get_fullname, strip_html_tags, markdown
from frappe.website.utils import find_first_image, get_comment_list

class BlogPost(WebsiteGenerator):
	website = frappe._dict(
		order_by = "published_on desc"
	)

	def make_route(self):
		if not self.route:
			return frappe.db.get_value('Blog Category', self.blog_category,
				'route') + '/' + self.scrub(self.title)

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
		clear_cache("writers")

	def get_context(self, context):
		# this is for double precaution. usually it wont reach this code if not published
		if not cint(self.published):
			raise Exception("This blog has not been published yet!")

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
		if not context.comment_list:
			context.comment_text = _('No comments yet')
		else:
			if(len(context.comment_list)) == 1:
				context.comment_text = _('1 comment')
			else:
				context.comment_text = _('{0} comments').format(len(context.comment_list))

		context.category = frappe.db.get_value("Blog Category",
			context.doc.blog_category, ["title", "route"], as_dict=1)
		context.parents = [{"name": _("Home"), "route":"/"},
			{"name": "Blog", "route": "/blog"},
			{"label": context.category.title, "route":context.category.route}]

def get_list_context(context=None):
	list_context = frappe._dict(
		template = "templates/includes/blog/blog.html",
		get_list = get_blog_list,
		hide_filters = True,
		children = get_children(),
		# show_search = True,
		title = _('Blog')
	)

	category = frappe.local.form_dict.blog_category or frappe.local.form_dict.category
	if category:
		category_title = get_blog_category(category)
		list_context.sub_title = _("Posts filed under {0}").format(category_title)
		list_context.title = category_title

	elif frappe.local.form_dict.blogger:
		blogger = frappe.db.get_value("Blogger", {"name": frappe.local.form_dict.blogger}, "full_name")
		list_context.sub_title = _("Posts by {0}").format(blogger)
		list_context.title = blogger

	elif frappe.local.form_dict.txt:
		list_context.sub_title = _('Filtered by "{0}"').format(frappe.local.form_dict.txt)

	if list_context.sub_title:
		list_context.parents = [{"name": _("Home"), "route": "/"},
								{"name": "Blog", "route": "/blog"}]
	else:
		list_context.parents = [{"name": _("Home"), "route": "/"}]

	list_context.update(frappe.get_doc("Blog Settings", "Blog Settings").as_dict(no_default_fields=True))
	return list_context

def get_children():
	return frappe.db.sql("""select route as name,
		title from `tabBlog Category`
		where published = 1
		and exists (select name from `tabBlog Post`
			where `tabBlog Post`.blog_category=`tabBlog Category`.name and published=1)
		order by title asc""", as_dict=1)

def clear_blog_cache():
	for blog in frappe.db.sql_list("""select route from
		`tabBlog Post` where ifnull(published,0)=1"""):
		clear_cache(blog)

	clear_cache("writers")

def get_blog_category(route):
	return frappe.db.get_value("Blog Category", {"name": route}, "title") or route

def get_blog_list(doctype, txt=None, filters=None, limit_start=0, limit_page_length=20, order_by=None):
	conditions = []
	if filters:
		if filters.blogger:
			conditions.append('t1.blogger="%s"' % frappe.db.escape(filters.blogger))
		if filters.blog_category:
			conditions.append('t1.blog_category="%s"' % frappe.db.escape(filters.blog_category))

	if txt:
		conditions.append('(t1.content like "%{0}%" or t1.title like "%{0}%")'.format(frappe.db.escape(txt)))

	if conditions:
		frappe.local.no_cache = 1

	query = """\
		select
			t1.title, t1.name, t1.blog_category, t1.route, t1.published_on,
				t1.published_on as creation,
				t1.content as content,
				ifnull(t1.blog_intro, t1.content) as intro,
				t2.full_name, t2.avatar, t1.blogger,
				(select count(name) from `tabCommunication`
					where
						communication_type='Comment'
						and comment_type='Comment'
						and reference_doctype='Blog Post'
						and reference_name=t1.name) as comments
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
		post.cover_image = find_first_image(post.content)
		post.published = global_date_format(post.creation)
		post.content = strip_html_tags(post.content[:340])
		if not post.comments:
			post.comment_text = _('No comments yet')
		elif post.comments==1:
			post.comment_text = _('1 comment')
		else:
			post.comment_text = _('{0} comments').format(str(post.comments))

		post.avatar = post.avatar or ""
		post.category = frappe.db.get_value('Blog Category', post.blog_category,
			['route', 'title'], as_dict=True)

		if post.avatar and (not "http:" in post.avatar and not "https:" in post.avatar) and not post.avatar.startswith("/"):
			post.avatar = "/" + post.avatar

	return posts
