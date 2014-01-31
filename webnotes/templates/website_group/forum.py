# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes.utils import now_datetime, get_datetime_str
from webnotes.webutils import get_access
from webnotes.templates.generators.website_group import get_views

def get_views():
	return views
	
def get_context(group_context):
	return {
		"post_list_html": get_post_list_html(group_context["group"]["name"], group_context["view"])
	}

@webnotes.whitelist(allow_guest=True)
def get_post_list_html(group, view, limit_start=0, limit_length=20):
	access = get_access(group)
	
	if isinstance(view, basestring):
		view = get_views(group)["view"]
	
	view = webnotes._dict(view)
	
	# verify permission for paging
	if webnotes.local.form_dict.cmd == "get_post_list_html":
		if not access.get("read"):
			return webnotes.PermissionError
			
	if view.name == "feed":
		order_by = "p.creation desc"
	else:
		now = get_datetime_str(now_datetime())
		order_by = """(p.upvotes + post_reply_count - (timestampdiff(hour, p.creation, \"{}\") / 2)) desc, 
			p.creation desc""".format(now)
	
	posts = webnotes.conn.sql("""select p.*, pr.user_image, pr.first_name, pr.last_name,
		(select count(pc.name) from `tabPost` pc where pc.parent_post=p.name) as post_reply_count
		from `tabPost` p, `tabProfile` pr
		where p.website_group = %s and pr.name = p.owner and ifnull(p.parent_post, '')=''
		order by {order_by} limit %s, %s""".format(order_by=order_by),
		(group, int(limit_start), int(limit_length)), as_dict=True)
		
	context = {"posts": posts, "limit_start": limit_start, "view": view}
	
	return webnotes.get_template("templates/includes/post_list.html").render(context)
	
views = {
	"popular": {
		"name": "popular",
		"template_path": "templates/unit_templates/forum_list.html",
		"url": "/{group}",
		"label": "Popular",
		"icon": "icon-heart",
		"default": True,
		"upvote": True,
		"idx": 1
	},
	"feed": {
		"name": "feed",
		"template_path": "templates/unit_templates/forum_list.html",
		"url": "/{group}?view=feed",
		"label": "Feed",
		"icon": "icon-rss",
		"upvote": True,
		"idx": 2
	},
	"post": {
		"name": "post",
		"template_path": "templates/unit_templates/base_post.html",
		"url": "/{group}?view=post&name={post}",
		"label": "Post",
		"icon": "icon-comments",
		"upvote": True,
		"hidden": True,
		"no_cache": True,
		"idx": 3
	},
	"edit": {
		"name": "edit",
		"template_path": "templates/unit_templates/base_edit.html",
		"url": "/{group}?view=edit&name={post}",
		"label": "Edit Post",
		"icon": "icon-pencil",
		"hidden": True,
		"no_cache": True,
		"idx": 4
	},
	"add": {
		"name": "add",
		"template_path": "templates/unit_templates/base_edit.html",
		"url": "/{group}?view=add",
		"label": "Add Post",
		"icon": "icon-plus",
		"hidden": True,
		"idx": 5
	},
	"settings": {
		"name": "settings",
		"template_path": "templates/unit_templates/base_settings.html",
		"url": "/{group}&view=settings",
		"label": "Settings",
		"icon": "icon-cog",
		"hidden": True,
		"idx": 6
	}
}