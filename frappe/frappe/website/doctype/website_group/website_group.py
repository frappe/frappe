# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.website.website_generator import WebsiteGenerator
from frappe.website.render import can_cache
from frappe.templates.website_group.forum import get_post_list_html
from frappe.utils.nestedset import NestedSet

class WebsiteGroup(WebsiteGenerator, NestedSet):
	no_cache = True
	template = "templates/generators/website_group.html"
	parent_website_route_field = "parent_website_group"
	page_title_field = "group_title"

	def on_update(self):
		WebsiteGenerator.on_update(self)
		NestedSet.on_update(self)
		clear_cache(website_group=self.name)

	def on_trash(self):
		WebsiteGenerator.on_trash(self)
		NestedSet.on_trash(self)

	def after_insert(self):
		clear_cache(website_group=self.name)

	def get_context(self, context):
		group, view = guess_group_view(context)

		try:
			if not has_access(context.access, view):
				raise frappe.PermissionError

			return get_group_context(group, view, context)

		except frappe.DoesNotExistError:
			return {
				"content": '<div class="alert alert-danger full-page">'
					'The page you are looking for does not exist.</div>'
				}
		except frappe.PermissionError:
			return {
				"content": '<div class="alert alert-danger full-page">'
					'You are not permitted to view this page.</div>'
			}

		return context


def get_group_context(group, view, context):
	cache_key = "website_group_context:{}:{}".format(group, view)

	views = get_views(context.doc.group_type)
	view = frappe._dict(views.get(view))

	if can_cache(view.no_cache):
		group_context = frappe.cache().get_value(cache_key)
		if group_context:
			return group_context

	group_context = build_group_context(group, view, views, context)

	if can_cache(view.get("no_cache")):
		frappe.cache().set_value(cache_key, group_context)

	group_context.children = context.doc.get_children()

	return group_context

def build_group_context(group, view, views, context):
	title = "{} - {}".format(context.doc.group_title, view.get("label"))

	group_context = frappe._dict({
		"group": context.doc,
		"view": view,
		"views": [v[1] for v in sorted(views.iteritems(), key=lambda (k, v): v.get("idx"))],
		"title": title,
		"pathname": context.pathname
	})
	group_context.update(build_view_context(group_context))

	return group_context

def build_view_context(context):
	from frappe.templates.website_group.post import get_post_context

	if context.view.name in ("popular", "feed", "open", "closed", "upcoming", "past"):
		context.post_list_html = get_post_list_html(context.group.name, context.view.name)

	elif context.view.name == "edit":
		context.post = frappe.get_doc("Post", frappe.form_dict.name).as_dict()

		if context.post.assigned_to:
			context.user = frappe.get_doc("User", context.post.assigned_to)

	elif context.view.name == "settings":
		context.users = frappe.db.sql("""select p.*, wsp.`read`, wsp.`write`, wsp.`admin`
			from `tabUser` p, `tabWebsite Route Permission` wsp
			where wsp.website_route=%s and wsp.user=p.name""", context.pathname, as_dict=True)

	elif context.view.name == "post":
		context.update(get_post_context(context))

	return context

def guess_group_view(context):
	group = context.docname
	view = frappe.form_dict.view or get_default_view(context.doc.group_type)
	return group, view

def get_default_view(group_type):
	for view, opts in get_views(group_type).iteritems():
		if opts.get("default"):
			return view

def get_views(group_type=None):
	if group_type:
		group_views = frappe._dict(views[group_type])
	else:
		group_views = {}
		for group_type in views:
			group_views.update(views[group_type].copy())

	group_views.update(common_views)

	if group_type == "Forum":
		group_views["post"]["upvote"] = True

	return group_views

def has_access(access, view):
	if view=="settings":
		return access.get("admin")
	elif view in ("add", "edit"):
		return access.get("write")
	else:
		return access.get("read")

def clear_cache(website_group=None):
	from frappe.templates.website_group.post import clear_post_cache
	if website_group:
		website_groups = [website_group]
	else:
		clear_post_cache()
		website_groups = frappe.db.sql_list("""select name from `tabWebsite Group`""")

	cache = frappe.cache()
	all_views = get_views()
	for group in website_groups:
		for view in all_views:
			cache.delete_value("website_group_context:{}:{}".format(group, view))

def clear_event_cache():
	for group in frappe.db.sql_list("""select name from `tabWebsite Group` where group_type='Event'"""):
		clear_cache(website_group=group)

views = {
	"Forum": {
		"popular": {
			"name": "popular",
			"template_path": "templates/website_group/forum.html",
			"label": "Popular",
			"icon": "icon-heart",
			"default": True,
			"upvote": True,
			"idx": 1
		},
		"feed": {
			"name": "feed",
			"template_path": "templates/website_group/forum.html",
			"label": "Feed",
			"icon": "icon-rss",
			"upvote": True,
			"idx": 2
		}
	},
	"Tasks": {
		"open": {
			"name": "open",
			"template_path": "templates/website_group/forum.html",
			"label": "Open",
			"icon": "icon-inbox",
			"default": True,
			"upvote": True,
			"idx": 1
		},
		"closed": {
			"name": "closed",
			"template_path": "templates/website_group/forum.html",
			"label": "Closed",
			"icon": "icon-smile",
			"idx": 2
		}
	},
	"Events": {
		"upcoming": {
			"name": "upcoming",
			"template_path": "templates/website_group/forum.html",
			"label": "Upcoming",
			"icon": "icon-calendar",
			"default": True,
			"idx": 1
		},
		"past": {
			"name": "past",
			"template_path": "templates/website_group/forum.html",
			"label": "Past",
			"icon": "icon-time",
			"idx": 2
		}
	}
}

common_views = {
	"post": {
		"name": "post",
		"template_path": "templates/website_group/post.html",
		"label": "Post",
		"icon": "icon-comments",
		"hidden": True,
		"no_cache": True,
		"idx": 3
	},
	"edit": {
		"name": "edit",
		"template_path": "templates/website_group/edit_post.html",
		"label": "Edit Post",
		"icon": "icon-pencil",
		"hidden": True,
		"no_cache": True,
		"idx": 4
	},
	"add": {
		"name": "add",
		"template_path": "templates/website_group/edit_post.html",
		"label": "Add Post",
		"icon": "icon-plus",
		"hidden": True,
		"idx": 5
	},
	"settings": {
		"name": "settings",
		"template_path": "templates/website_group/settings.html",
		"label": "Settings",
		"icon": "icon-cog",
		"hidden": True,
		"idx": 6
	}
}
