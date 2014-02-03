# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes.utils import get_fullname

def get_post_context(group_context):
	post = webnotes.doc("Post", webnotes.form_dict.name)
	if post.parent_post:
		raise webnotes.PermissionError
	
	fullname = get_fullname(post.owner)
	return {
		"title": "{} by {}".format(post.title, fullname),
		# "group_title": group_context.get("unit_title") + " by {}".format(fullname),
		"parent_post_html": get_parent_post_html(post, group_context.get("view")),
		"post_list_html": get_child_posts_html(post, group_context.get("view")),
		"parent_post": post.name
	}
	
def get_parent_post_html(post, view):
	profile = webnotes.bean("Profile", post.owner).doc
	for fieldname in ("first_name", "last_name", "user_image", "fb_hometown", "fb_location"):
		post.fields[fieldname] = profile.fields[fieldname]
	
	return webnotes.get_template("templates/includes/inline_post.html")\
		.render({"post": post.fields, "view": view})

def get_child_posts_html(post, view):
	posts = webnotes.conn.sql("""select p.*, pr.user_image, pr.first_name, pr.last_name
		from tabPost p, tabProfile pr
		where p.parent_post=%s and pr.name = p.owner
		order by p.creation asc""", (post.name,), as_dict=True)
			
	return webnotes.get_template("templates/includes/post_list.html")\
		.render({
			"posts": posts,
			"parent_post": post.name,
			"view": view
		})