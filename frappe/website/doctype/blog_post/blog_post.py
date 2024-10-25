# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from math import ceil

import frappe
from frappe import _
from frappe.utils import (
	cint,
	get_fullname,
	global_date_format,
	markdown,
	sanitize_html,
	strip_html_tags,
	today,
)
from frappe.website.utils import (
	clear_cache,
	find_first_image,
	get_comment_list,
	get_html_content_based_on_type,
)
from frappe.website.website_generator import WebsiteGenerator


class BlogPost(WebsiteGenerator):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		blog_category: DF.Link
		blog_intro: DF.SmallText | None
		blogger: DF.Link
		content: DF.TextEditor | None
		content_html: DF.HTMLEditor | None
		content_md: DF.MarkdownEditor | None
		content_type: DF.Literal["Markdown", "Rich Text", "HTML"]
		disable_comments: DF.Check
		disable_likes: DF.Check
		email_sent: DF.Check
		enable_email_notification: DF.Check
		featured: DF.Check
		hide_cta: DF.Check
		meta_description: DF.SmallText | None
		meta_image: DF.AttachImage | None
		meta_title: DF.Data | None
		published: DF.Check
		published_on: DF.Date | None
		read_time: DF.Int
		route: DF.Data | None
		title: DF.Data
	# end: auto-generated types

	@frappe.whitelist()
	def make_route(self):
		if not self.route:
			return (
				frappe.db.get_value("Blog Category", self.blog_category, "route")
				+ "/"
				+ self.scrub(self.title)
			)

	def validate(self) -> None:
		super().validate()

		if not self.blog_intro:
			content = get_html_content_based_on_type(self, "content", self.content_type)
			self.blog_intro = content[:200]
			self.blog_intro = strip_html_tags(self.blog_intro)

		if self.blog_intro:
			self.blog_intro = self.blog_intro[:200]

		if not self.meta_title:
			self.meta_title = self.title[:60]
		else:
			self.meta_title = self.meta_title[:60]

		if not self.meta_description:
			self.meta_description = self.blog_intro[:140]
		else:
			self.meta_description = self.meta_description[:140]

		if self.published and not self.published_on:
			self.published_on = today()

		if self.featured:
			if not self.meta_image:
				frappe.throw(_("A featured post must have a cover image"))
			self.reset_featured_for_other_blogs()

		self.set_read_time()

		if self.is_website_published():
			from frappe.core.doctype.file.utils import extract_images_from_doc

			# Extract images first before the standard image extraction to ensure they are public.
			extract_images_from_doc(self, "content", is_private=False)

	def reset_featured_for_other_blogs(self) -> None:
		all_posts = frappe.get_all("Blog Post", {"featured": 1})
		for post in all_posts:
			frappe.db.set_value("Blog Post", post.name, "featured", 0)

	def on_update(self) -> None:
		super().on_update()
		clear_cache("writers")

	def on_trash(self) -> None:
		super().on_trash()

	def get_context(self, context):
		# this is for double precaution. usually it wont reach this code if not published
		if not cint(self.published):
			raise Exception("This blog has not been published yet!")

		context.no_breadcrumbs = True

		# temp fields
		context.full_name = get_fullname(self.owner)
		context.updated = global_date_format(self.published_on)
		context.social_links = self.fetch_social_links_info()
		context.cta = self.fetch_cta()
		context.enable_cta = not self.hide_cta and frappe.db.get_single_value(
			"Blog Settings", "show_cta_in_blog", cache=True
		)

		if self.blogger:
			context.blogger_info = frappe.get_doc("Blogger", self.blogger).as_dict()
			context.author = self.blogger

		context.content = get_html_content_based_on_type(self, "content", self.content_type)

		# if meta description is not present, then blog intro or first 140 characters of the blog will be set as description
		context.description = (
			self.meta_description or self.blog_intro or strip_html_tags(context.content[:140])
		)

		context.metatags = {
			"name": self.meta_title,
			"description": context.description,
		}

		# if meta image is not present, then first image inside the blog will be set as the meta image
		image = find_first_image(context.content)
		context.metatags["image"] = self.meta_image or image or None

		self.load_comments(context)
		self.load_likes(context)

		context.category = frappe.db.get_value(
			"Blog Category", context.doc.blog_category, ["title", "route"], as_dict=1
		)
		context.parents = [
			{"name": _("Home"), "route": "/"},
			{"name": "Blog", "route": "/blog"},
			{"label": context.category.title, "route": context.category.route},
		]
		context.guest_allowed = frappe.db.get_single_value("Blog Settings", "allow_guest_to_comment")

	def fetch_cta(self):
		if frappe.db.get_single_value("Blog Settings", "show_cta_in_blog", cache=True):
			blog_settings = frappe.get_cached_doc("Blog Settings")

			return {
				"show_cta_in_blog": 1,
				"title": blog_settings.title,
				"subtitle": blog_settings.subtitle,
				"cta_label": blog_settings.cta_label,
				"cta_url": blog_settings.cta_url,
			}

		return {}

	def fetch_social_links_info(self):
		if not frappe.db.get_single_value("Blog Settings", "enable_social_sharing", cache=True):
			return []

		url = frappe.local.site + "/" + self.route

		return [
			{
				"icon": "twitter",
				"link": "https://twitter.com/intent/tweet?text=" + self.title + "&url=" + url,
			},
			{
				"icon": "facebook",
				"link": "https://www.facebook.com/sharer.php?u=" + url,
			},
			{
				"icon": "linkedin",
				"link": "https://www.linkedin.com/sharing/share-offsite/?url=" + url,
			},
			{
				"icon": "envelope",
				"link": "mailto:?subject=" + self.title + "&body=" + url,
			},
		]

	def load_comments(self, context) -> None:
		context.comment_list = get_comment_list(self.doctype, self.name)

		if not context.comment_list:
			context.comment_count = 0
		else:
			context.comment_count = len(context.comment_list)

	def load_likes(self, context) -> None:
		user = frappe.session.user

		filters = {
			"comment_type": "Like",
			"reference_doctype": self.doctype,
			"reference_name": self.name,
		}

		context.like_count = frappe.db.count("Comment", filters)

		filters["comment_email"] = user

		if user == "Guest":
			filters["ip_address"] = frappe.local.request_ip

		context.like = frappe.db.count("Comment", filters)

	def set_read_time(self) -> None:
		content = self.content or self.content_html or ""
		if self.content_type == "Markdown":
			content = markdown(self.content_md)

		total_words = len(strip_html_tags(content).split())
		self.read_time = ceil(total_words / 250)


def get_list_context(context=None):
	list_context = frappe._dict(
		get_list=get_blog_list,
		no_breadcrumbs=True,
		hide_filters=True,
		# show_search = True,
		title=_("Blog"),
	)

	blog_settings = frappe.get_doc("Blog Settings").as_dict(no_default_fields=True)
	list_context.update(blog_settings)

	category_name = frappe.utils.escape_html(
		frappe.local.form_dict.blog_category or frappe.local.form_dict.category
	)
	if category_name:
		category = frappe.get_doc("Blog Category", category_name)
		list_context.blog_introduction = category.description or _("Posts filed under {0}").format(
			category.title
		)
		list_context.blog_title = category.title
		list_context.preview_image = category.preview_image

	elif frappe.local.form_dict.blogger:
		blogger = frappe.db.get_value("Blogger", {"name": frappe.local.form_dict.blogger}, "full_name")
		list_context.sub_title = _("Posts by {0}").format(blogger)
		list_context.title = blogger

	elif frappe.local.form_dict.txt:
		list_context.sub_title = _('Filtered by "{0}"').format(sanitize_html(frappe.local.form_dict.txt))

	if list_context.sub_title:
		list_context.parents = [{"name": _("Home"), "route": "/"}, {"name": "Blog", "route": "/blog"}]
	else:
		list_context.parents = [{"name": _("Home"), "route": "/"}]

	if blog_settings.browse_by_category:
		list_context.blog_categories = get_blog_categories()

	list_context.metatags = {
		"name": list_context.blog_title,
		"title": list_context.blog_title,
		"description": list_context.blog_introduction,
		"image": list_context.preview_image,
	}

	return list_context


def get_blog_categories():
	from pypika import Order
	from pypika.terms import ExistsCriterion

	post, category = frappe.qb.DocType("Blog Post"), frappe.qb.DocType("Blog Category")
	return (
		frappe.qb.from_(category)
		.select(category.name, category.route, category.title)
		.where(
			(category.published == 1)
			& ExistsCriterion(
				frappe.qb.from_(post)
				.select("name")
				.where((post.published == 1) & (post.blog_category == category.name))
			)
		)
		.orderby(category.title, order=Order.asc)
		.run(as_dict=1)
	)


def clear_blog_cache() -> None:
	for blog in frappe.db.get_list("Blog Post", fields=["route"], pluck="route", filters={"published": True}):
		clear_cache(blog)

	clear_cache("writers")


def get_blog_list(
	doctype, txt=None, filters=None, limit_start: int = 0, limit_page_length: int = 20, order_by=None
):
	conditions = []
	if filters and filters.get("blog_category"):
		category = filters.get("blog_category")
	else:
		category = frappe.utils.escape_html(
			frappe.local.form_dict.blog_category or frappe.local.form_dict.category
		)

	if filters and filters.get("blogger"):
		conditions.append("t1.blogger=%s" % frappe.db.escape(filters.get("blogger")))

	if category:
		conditions.append("t1.blog_category=%s" % frappe.db.escape(category))

	if txt:
		conditions.append(
			'(t1.content like {0} or t1.title like {0}")'.format(frappe.db.escape("%" + txt + "%"))
		)

	if conditions:
		frappe.local.no_cache = 1

	query = """\
		select
			t1.title, t1.name, t1.blog_category, t1.route, t1.published_on, t1.read_time,
				t1.published_on as creation,
				t1.read_time as read_time,
				t1.featured as featured,
				t1.meta_image as cover_image,
				t1.content as content,
				t1.content_type as content_type,
				t1.content_html as content_html,
				t1.content_md as content_md,
				ifnull(t1.blog_intro, t1.content) as intro,
				t2.full_name, t2.avatar, t1.blogger,
				(select count(name) from `tabComment`
					where
						comment_type='Comment'
						and reference_doctype='Blog Post'
						and reference_name=t1.name) as comments
		from `tabBlog Post` t1, `tabBlogger` t2
		where t1.published = 1
		and t1.blogger = t2.name
		{condition}
		order by featured desc, published_on desc, name asc
		limit {page_len} OFFSET {start}""".format(
		start=limit_start,
		page_len=limit_page_length,
		condition=(" and " + " and ".join(conditions)) if conditions else "",
	)

	posts = frappe.db.sql(query, as_dict=1)

	for post in posts:
		post.content = get_html_content_based_on_type(post, "content", post.content_type)
		if not post.cover_image:
			post.cover_image = find_first_image(post.content)
		post.published = global_date_format(post.creation)
		post.content = strip_html_tags(post.content)

		if not post.comments:
			post.comment_text = _("No comments yet")
		elif post.comments == 1:
			post.comment_text = _("1 comment")
		else:
			post.comment_text = _("{0} comments").format(str(post.comments))

		post.avatar = post.avatar or ""
		post.category = frappe.db.get_value(
			"Blog Category", post.blog_category, ["name", "route", "title"], as_dict=True
		)

		if (
			post.avatar
			and ("http:" not in post.avatar and "https:" not in post.avatar)
			and not post.avatar.startswith("/")
		):
			post.avatar = "/" + post.avatar

	return posts
