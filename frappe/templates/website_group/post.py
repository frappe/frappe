# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import get_fullname
from frappe.website.permissions import get_access
from frappe.utils.file_manager import save_file

def get_post_context(context):
	post = frappe.get_doc("Post", frappe.form_dict.name)
	if post.parent_post:
		raise frappe.PermissionError

	def _get_post_context():
		fullname = get_fullname(post.owner)
		return {
			"title": "{} by {}".format(post.title, fullname),
			"parent_post_html": get_parent_post_html(post, context),
			"post_list_html": get_child_posts_html(post, context),
			"parent_post": post.name
		}

	cache_key = "website_group_post:{}".format(post.name)
	return frappe.cache().get_value(cache_key, lambda: _get_post_context())

def get_parent_post_html(post, context):
	user = frappe.get_doc("User", post.owner)
	for fieldname in ("first_name", "last_name", "user_image", "location"):
		post.set(fieldname, user.get(fieldname))

	return frappe.get_template("templates/includes/inline_post.html")\
		.render({"post": post, "view": context.view})

def get_child_posts_html(post, context):
	posts = frappe.db.sql("""select p.*, pr.user_image, pr.first_name, pr.last_name
		from tabPost p, tabUser pr
		where p.parent_post=%s and pr.name = p.owner
		order by p.creation asc""", (post.name,), as_dict=True)

	return frappe.get_template("templates/includes/post_list.html")\
		.render({
			"posts": posts,
			"parent_post": post.name,
			"view": context.view
		})

def clear_post_cache(post=None):
	cache = frappe.cache()
	posts = [post] if post else frappe.db.sql_list("select name from `tabPost`")

	for post in posts:
		cache.delete_value("website_group_post:{}".format(post))

@frappe.whitelist(allow_guest=True)
def add_post(group, content, picture, picture_name, title=None, parent_post=None,
	assigned_to=None, status=None, event_datetime=None):

	doc = frappe.get_doc("Website Group", group)
	access = get_access(doc, doc.get_route())
	if not access.get("write"):
		raise frappe.PermissionError

	if parent_post:
		if frappe.db.get_value("Post", parent_post, "parent_post"):
			frappe.throw(_("Cannot reply to a reply"))

	group = frappe.get_doc("Website Group", group)
	post = frappe.get_doc({
		"doctype":"Post",
		"title": (title or "").title(),
		"content": content,
		"website_group": group.name,
		"parent_post": parent_post or None
	})

	if not parent_post:
		if group.group_type == "Tasks":
			post.is_task = 1
			post.assigned_to = assigned_to
		elif group.group_type == "Events":
			post.is_event = 1
			post.event_datetime = event_datetime

	post.ignore_permissions = True
	post.insert()

	if picture_name and picture:
		process_picture(post, picture_name, picture)

	# send email
	if parent_post:
		post.run_method("send_email_on_reply")

	return post.parent_post or post.name

@frappe.whitelist(allow_guest=True)
def save_post(post, content, picture=None, picture_name=None, title=None,
	assigned_to=None, status=None, event_datetime=None):

	post = frappe.get_doc("Post", post)
	group = frappe.get_doc("Website Group", post.website_group)
	access = get_access(group, group.get_route())

	if not access.get("write"):
		raise frappe.PermissionError

	# TODO improve error message
	if frappe.session.user != post.owner:
		for fieldname in ("title", "content"):
			if post.get(fieldname) != locals().get(fieldname):
				frappe.throw(_("Cannot change {0}").format(fieldname))

		if picture and picture_name:
			frappe.throw(_("Cannot change picture"))

	post.update({
		"title": (title or "").title(),
		"content": content,
		"assigned_to": assigned_to,
		"status": status,
		"event_datetime": event_datetime
	})
	post.ignore_permissions = True
	post.save()

	if picture_name and picture:
		process_picture(post, picture_name, picture)

	return post.parent_post or post.name

def process_picture(post, picture_name, picture):
	from frappe.website.doctype.website_group.website_group import clear_cache

	post.picture_url = save_file(picture_name, picture, "Post", post.name, decode=True).file_url
	frappe.db.set_value("Post", post.name, "picture_url", post.picture_url)
	clear_cache(website_group=post.website_group)

@frappe.whitelist()
def suggest_user(group, term):
	"""suggest a user that has read permission in this group tree"""
	users = frappe.db.sql("""select
		pr.name, pr.first_name, pr.last_name,
		pr.user_image, pr.location
		from `tabUser` pr
		where (pr.first_name like %(term)s or pr.last_name like %(term)s)
		and pr.user_type = 'Website User' and pr.enabled=1""",
		{"term": "%{}%".format(term), "group": group}, as_dict=True)

	template = frappe.get_template("templates/includes/user_display.html")
	return [{
		"value": "{} {}".format(pr.first_name or "", pr.last_name or "").strip(),
		"user_html": template.render({"user": pr}),
		"user": pr.name
	} for pr in users]
