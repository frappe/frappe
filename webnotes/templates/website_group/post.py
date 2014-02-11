# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes.utils import get_fullname
from webnotes.webutils import get_access
from webnotes.utils.file_manager import save_file
from webnotes.templates.generators.website_group import get_pathname

def get_post_context(context):
	post = webnotes.doc("Post", webnotes.form_dict.name)
	if post.parent_post:
		raise webnotes.PermissionError
		
	def _get_post_context():
		fullname = get_fullname(post.owner)
		return {
			"title": "{} by {}".format(post.title, fullname),
			"parent_post_html": get_parent_post_html(post, context),
			"post_list_html": get_child_posts_html(post, context),
			"parent_post": post.name
		}
	
	cache_key = "website_group_post:{}".format(post.name)
	return webnotes.cache().get_value(cache_key, lambda: _get_post_context())
	
def get_parent_post_html(post, context):
	profile = webnotes.bean("Profile", post.owner).doc
	for fieldname in ("first_name", "last_name", "user_image", "location"):
		post.fields[fieldname] = profile.fields[fieldname]
	
	return webnotes.get_template("templates/includes/inline_post.html")\
		.render({"post": post.fields, "view": context.view})

def get_child_posts_html(post, context):
	posts = webnotes.conn.sql("""select p.*, pr.user_image, pr.first_name, pr.last_name
		from tabPost p, tabProfile pr
		where p.parent_post=%s and pr.name = p.owner
		order by p.creation asc""", (post.name,), as_dict=True)
			
	return webnotes.get_template("templates/includes/post_list.html")\
		.render({
			"posts": posts,
			"parent_post": post.name,
			"view": context.view
		})
		
def clear_post_cache(post=None):
	cache = webnotes.cache()
	posts = [post] if post else webnotes.conn.sql_list("select name from `tabPost`")

	for post in posts:
		cache.delete_value("website_group_post:{}".format(post))
		
@webnotes.whitelist(allow_guest=True)
def add_post(group, content, picture, picture_name, title=None, parent_post=None, 
	assigned_to=None, status=None, event_datetime=None):
	
	access = get_access(get_pathname(group))
	if not access.get("write"):
		raise webnotes.PermissionError

	if parent_post:
		if webnotes.conn.get_value("Post", parent_post, "parent_post"):
			webnotes.throw("Cannot reply to a reply")
		
	group = webnotes.doc("Website Group", group)	
	post = webnotes.bean({
		"doctype":"Post",
		"title": (title or "").title(),
		"content": content,
		"website_group": group.name,
		"parent_post": parent_post or None
	})
	
	if not parent_post:
		if group.group_type == "Tasks":
			post.doc.is_task = 1
			post.doc.assigned_to = assigned_to
		elif group.group_type == "Events":
			post.doc.is_event = 1
			post.doc.event_datetime = event_datetime
	
	post.ignore_permissions = True
	post.insert()

	if picture_name and picture:
		process_picture(post, picture_name, picture)
	
	# send email
	if parent_post:
		post.run_method("send_email_on_reply")
		
	return post.doc.parent_post or post.doc.name
		
@webnotes.whitelist(allow_guest=True)
def save_post(post, content, picture=None, picture_name=None, title=None,
	assigned_to=None, status=None, event_datetime=None):
	
	post = webnotes.bean("Post", post)
	access = get_access(get_pathname(post.doc.website_group))
	
	if not access.get("write"):
		raise webnotes.PermissionError
	
	# TODO improve error message
	if webnotes.session.user != post.doc.owner:
		for fieldname in ("title", "content"):
			if post.doc.fields.get(fieldname) != locals().get(fieldname):
				webnotes.throw("You cannot change: {}".format(fieldname.title()))
				
		if picture and picture_name:
			webnotes.throw("You cannot change: Picture")
			
	post.doc.fields.update({
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
		
	return post.doc.parent_post or post.doc.name
		
def process_picture(post, picture_name, picture):
	from webnotes.templates.generators.website_group import clear_cache
	
	file_data = save_file(picture_name, picture, "Post", post.doc.name, decode=True)
	post.doc.picture_url = file_data.file_name or file_data.file_url
	webnotes.conn.set_value("Post", post.doc.name, "picture_url", post.doc.picture_url)
	clear_cache(website_group=post.doc.website_group)
	
@webnotes.whitelist()
def suggest_user(group, term):
	"""suggest a user that has read permission in this group tree"""
	profiles = webnotes.conn.sql("""select 
		pr.name, pr.first_name, pr.last_name, 
		pr.user_image, pr.location
		from `tabProfile` pr
		where (pr.first_name like %(term)s or pr.last_name like %(term)s)
		and pr.user_type = 'Website User' and pr.enabled=1""", 
		{"term": "%{}%".format(term), "group": group}, as_dict=True)
	
	template = webnotes.get_template("templates/includes/profile_display.html")
	return [{
		"value": "{} {}".format(pr.first_name or "", pr.last_name or "").strip(), 
		"profile_html": template.render({"profile": pr}),
		"profile": pr.name
	} for pr in profiles]
