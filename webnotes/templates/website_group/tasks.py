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
	tasks_context = {}
	
	if group_context.view.name in ("open", "closed"):
		tasks_context["post_list_html"] = get_post_list_html(group_context["group"]["name"], group_context["view"])
	
	elif group_context.view.name == "edit":
		post = webnotes.doc("Post", webnotes.form_dict.name).fields
		tasks_context["session_user"] = webnotes.session.user
		tasks_context["post"] = post
		if post.assigned_to:
			tasks_context["profile"] = webnotes.doc("Profile", post.assigned_to)

	elif group_context.view.name == "settings":
		tasks_context.update(get_settings_context(group_context))
		
	elif group_context.view.name == "post":
		tasks_context.update(get_post_context(group_context))
	
	return tasks_context
	
@webnotes.whitelist(allow_guest=True)
def get_post_list_html(group, view, limit_start=0, limit_length=20, status="Open"):
	access = get_access(group)
	
	if isinstance(view, basestring):
		view = get_views()[view]
	
	view = webnotes._dict(view)
	
	# verify permission for paging
	if webnotes.local.form_dict.cmd == "get_post_list_html":
		if not access.get("read"):
			return webnotes.PermissionError
	
	if view.name=="open":
		now = get_datetime_str(now_datetime())
		order_by = "(p.upvotes + post_reply_count - (timestampdiff(hour, p.creation, \"{}\") / 2)) desc, p.creation desc".format(now)
	else:
		status = "Closed"
		order_by = "p.creation desc"
	
	posts = webnotes.conn.sql("""select p.*, pr.user_image, pr.first_name, pr.last_name,
		(select count(pc.name) from `tabPost` pc where pc.parent_post=p.name) as post_reply_count
		from `tabPost` p, `tabProfile` pr
		where p.website_group = %s and pr.name = p.owner and ifnull(p.parent_post, '')=''
		and p.is_task=1 and p.status=%s
		order by {order_by} limit %s, %s""".format(order_by=order_by),
		(group, status, int(limit_start), int(limit_length)), as_dict=True)
		
	context = {"posts": posts, "limit_start": limit_start, "view": view}
	
	return webnotes.get_template("templates/includes/post_list.html").render(context)
	
views = {
	"open": {
		"name": "open",
		"template_path": "templates/website_group/tasks.html",
		"url": "/{group}",
		"label": "Open",
		"icon": "icon-inbox",
		"default": True,
		"upvote": True,
		"idx": 1
	},
	"closed": {
		"name": "closed",
		"template_path": "templates/website_group/tasks.html",
		"url": "/{group}?view=closed",
		"label": "Closed",
		"icon": "icon-smile",
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
		"upvote": True,
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