# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import webnotes
from webnotes.webutils import get_access, can_cache
from webnotes.templates.website_group.forum import get_post_list_html

doctype = "Website Group"
no_cache = 1

def get_context(context):
	group, view = guess_group_view(context)
	
	try:
		if not has_access(context.access, view):
			raise webnotes.PermissionError
		
		return get_group_context(group, view, context)
	
	except webnotes.DoesNotExistError:
		return {
			"content": '<div class="alert alert-danger full-page">'
				'The page you are looking for does not exist.</div>'
			}
	except webnotes.PermissionError:
		return {
			"content": '<div class="alert alert-danger full-page">'
				'You are not permitted to view this page.</div>'
		}
		
def get_group_context(group, view, context):
	cache_key = "website_group_context:{}:{}".format(group, view)

	views = get_views(context.bean.doc.group_type)
	view = webnotes._dict(views.get(view))
	
	if can_cache(view.no_cache):
		group_context = webnotes.cache().get_value(cache_key)
		if group_context:
			return group_context
			
	group_context = build_group_context(group, view, views, context)
	
	if can_cache(view.get("no_cache")):
		webnotes.cache().set_value(cache_key, group_context)
		
	return group_context
	
def build_group_context(group, view, views, context):
	title = "{} - {}".format(context.bean.doc.group_title, view.get("label"))
	
	group_context = webnotes._dict({
		"group": context.bean.doc.fields,
		"view": view,
		"views": [v[1] for v in sorted(views.iteritems(), key=lambda (k, v): v.get("idx"))],
		"title": title,
		"pathname": context.pathname
	})
	group_context.update(build_view_context(group_context))
	
	return group_context
	
def build_view_context(context):
	from webnotes.templates.website_group.post import get_post_context
	
	if context.view.name in ("popular", "feed", "open", "closed", "upcoming", "past"):
		context.post_list_html = get_post_list_html(context.group.name, context.view.name)
	
	elif context.view.name == "edit":
		context.post = webnotes.doc("Post", webnotes.form_dict.name).fields
		
		if context.post.assigned_to:
			context.profile = webnotes.doc("Profile", context.post.assigned_to)

	elif context.view.name == "settings":
		context.profiles = webnotes.conn.sql("""select p.*, wsp.`read`, wsp.`write`, wsp.`admin`
			from `tabProfile` p, `tabWebsite Sitemap Permission` wsp
			where wsp.website_sitemap=%s and wsp.profile=p.name""", context.pathname, as_dict=True)
		
	elif context.view.name == "post":
		context.update(get_post_context(context))
		
	return context
	
def guess_group_view(context):
	group = context.docname
	view = webnotes.form_dict.view or get_default_view(context.bean.doc.group_type)
	return group, view
	
def get_default_view(group_type):
	for view, opts in get_views(group_type).iteritems():
		if opts.get("default"):
			return view
	
def get_views(group_type=None):
	if group_type:
		group_views = webnotes._dict(views[group_type])
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
		
def clear_cache(path=None, website_group=None):
	from webnotes.templates.website_group.post import clear_post_cache
	if path:
		website_groups = [webnotes.conn.get_value("Website Sitemap", path, "docname")]
	elif website_group:
		website_groups = [website_group]
	else:
		clear_post_cache()
		website_groups = webnotes.conn.sql_list("""select name from `tabWebsite Group`""")
	
	cache = webnotes.cache()
	all_views = get_views()
	for group in website_groups:
		for view in all_views:
			cache.delete_value("website_group_context:{}:{}".format(group, view))

def clear_event_cache():
	for group in webnotes.conn.sql_list("""select name from `tabWebsite Group` where group_type='Event'"""):
		clear_unit_views(website_group=group)
		
def clear_cache_on_bean_event(bean, method, *args, **kwargs):
	clear_cache(path=bean.doc.website_sitemap, website_group=bean.doc.website_group)
	
def get_pathname(group):
	return webnotes.conn.get_value("Website Sitemap", {"ref_doctype": "Website Group",
		"docname": group})

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