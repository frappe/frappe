# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes.utils import now_datetime, get_datetime_str
from webnotes.webutils import get_access
from webnotes.templates.website_group.settings import get_settings_context
from webnotes.templates.website_group.post import get_post_context

def get_views():
	return views
	
def get_context(group_context):
	events_context = {}
	
	if group_context.view.name in ("upcoming", "past"):
		events_context["post_list_html"] = get_post_list_html(group_context["group"]["name"], group_context["view"])
	
	elif group_context.view.name == "edit":
		events_context["session_user"] = webnotes.session.user
		events_context["post"] = webnotes.doc("Post", webnotes.form_dict.name).fields

	elif group_context.view.name == "settings":
		events_context.update(get_settings_context(group_context))
		
	elif group_context.view.name == "post":
		events_context.update(get_post_context(group_context))
	
	return events_context
	
@webnotes.whitelist(allow_guest=True)
def get_post_list_html(group, view, limit_start=0, limit_length=20):
	access = get_access(group)
	
	if isinstance(view, basestring):
		view = get_views()[view]
	
	view = webnotes._dict(view)
	
	# verify permission for paging
	if webnotes.local.form_dict.cmd == "get_post_list_html":
		if not access.get("read"):
			return webnotes.PermissionError
			
	if view.name=="upcoming":
		condition = "and p.event_datetime >= %s"
		order_by = "p.event_datetime asc"
	else:
		condition = "and p.event_datetime < %s"
		order_by = "p.event_datetime desc"
		
	# should show based on time upto precision of hour
	# because the current hour should also be in upcoming
	now = now_datetime().replace(minute=0, second=0, microsecond=0)
	
	posts = webnotes.conn.sql("""select p.*, pr.user_image, pr.first_name, pr.last_name,
		(select count(pc.name) from `tabPost` pc where pc.parent_post=p.name) as post_reply_count
		from `tabPost` p, `tabProfile` pr
		where p.website_group = %s and pr.name = p.owner and ifnull(p.parent_post, '')=''
		and p.is_event=1 {condition}
		order by {order_by} limit %s, %s""".format(condition=condition, order_by=order_by),
		(group, now, int(limit_start), int(limit_length)), as_dict=True)
		
	context = {"posts": posts, "limit_start": limit_start, "view": view}
	
	return webnotes.get_template("templates/includes/post_list.html").render(context)
	
views = {
	"upcoming": {
		"name": "upcoming",
		"template_path": "templates/website_group/events.html",
		"url": "/{group}",
		"label": "Upcoming",
		"icon": "icon-calendar",
		"default": True,
		"idx": 1
	},
	"past": {
		"name": "past",
		"template_path": "templates/website_group/events.html",
		"url": "/{group}?view=past",
		"label": "Past",
		"icon": "icon-time",
		"idx": 2
	},
	"post": {
		"name": "post",
		"template_path": "templates/website_group/post.html",
		"url": "/{group}?view=post&name={post}",
		"label": "Post",
		"icon": "icon-comments",
		"hidden": True,
		"no_cache": True,
		"idx": 3
	},
	"edit": {
		"name": "edit",
		"template_path": "templates/website_group/edit_post.html",
		"url": "/{group}?view=edit&name={post}",
		"label": "Edit Post",
		"icon": "icon-pencil",
		"hidden": True,
		"no_cache": True,
		"idx": 4
	},
	"add": {
		"name": "add",
		"template_path": "templates/website_group/edit_post.html",
		"url": "/{group}?view=add",
		"label": "Add Post",
		"icon": "icon-plus",
		"hidden": True,
		"idx": 5
	},
	"settings": {
		"name": "settings",
		"template_path": "templates/website_group/settings.html",
		"url": "/{group}?view=settings",
		"label": "Settings",
		"icon": "icon-cog",
		"hidden": True,
		"idx": 6
	}
}