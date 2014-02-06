# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals

import webnotes
from webnotes.utils import get_fullname
from webnotes.utils.email_lib.bulk import send
from webnotes.utils.email_lib import sendmail
from webnotes.utils.file_manager import save_file

from webnotes.webutils import get_access
from webnotes.templates.generators.website_group import clear_cache
from webnotes.templates.website_group.post import clear_post_cache

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def validate(self):
		if not self.doc.parent_post and not self.doc.title:
			webnotes.throw("Please enter title!")
		
		self.assigned_to = webnotes.conn.get_value(self.doc.doctype, self.doc.name, "assigned_to")
		if self.doc.is_task:
			if not self.doc.status:
				self.doc.status = "Open"
			if self.doc.assigned_to:
				if not self.doc.assigned_to_fullname:
					self.doc.assigned_to_fullname = get_fullname(self.doc.assigned_to)
			else:
				self.doc.assigned_to_fullname = None
		else:
			self.doc.assigned_to = self.doc.assigned_to_fullname = self.doc.status = None
			
		if self.doc.is_event:
			if not self.doc.event_datetime:
				webnotes.throw("Please specify Event's Date and Time")
		else:
			self.doc.event_datetime = None
			
	def on_update(self):
		clear_cache(website_group=self.doc.website_group)
		clear_post_cache(self.doc.parent_post or self.doc.name)

		if self.doc.assigned_to and self.doc.assigned_to != self.assigned_to \
			and webnotes.session.user != self.doc.assigned_to:
			
			# send assignment email
			sendmail(recipients=[self.doc.assigned_to], 
				subject="You have been assigned this Task by {}".format(get_fullname(self.doc.modified_by)),
				msg=self.get_reply_email_message(self.doc.name, get_fullname(self.doc.owner)))
		
	def send_email_on_reply(self):
		owner_fullname = get_fullname(self.doc.owner)
		
		parent_post = webnotes.bean("Post", self.doc.parent_post).doc
		
		message = self.get_reply_email_message(self.doc.name, owner_fullname)
		
		# send email to the owner of the post, if he/she is different
		if parent_post.owner != self.doc.owner:
			send(recipients=[parent_post.owner], 
				subject="{someone} replied to your post".format(someone=owner_fullname), 
				message=message,
			
				# to allow unsubscribe
				doctype='Post', 
				email_field='owner', 
				
				# for tracking sent status
				ref_doctype=self.doc.doctype, ref_docname=self.doc.name)
		
		# send email to members who part of the conversation
		participants = webnotes.conn.sql("""select owner, name from `tabPost`
			where parent_post=%s and owner not in (%s, %s) order by creation asc""", 
			(self.doc.parent_post, parent_post.owner, self.doc.owner), as_dict=True)
		
		send(recipients=[p.owner for p in participants], 
			subject="{someone} replied to a post by {other}".format(someone=owner_fullname, 
				other=get_fullname(parent_post.owner)), 
			message=message,
		
			# to allow unsubscribe
			doctype='Post',
			email_field='owner', 
			
			# for tracking sent status
			ref_doctype=self.doc.doctype, ref_docname=self.doc.name)
		
	def get_reply_email_message(self, post_name, owner_fullname=None):
		message = self.doc.content
		if self.doc.picture_url:
			message += """<div><img src="{url}" style="max-width: 100%"></div>"""\
				.format(url=self.doc.picture_url)
		message += "<p>By {fullname}</p>".format(fullname=owner_fullname)
		message += "<p><a href='/post/{post_name}'>Click here to view the post</a></p>".format(fullname=owner_fullname,
			post_name=post_name)
		return message
	
@webnotes.whitelist(allow_guest=True)
def add_post(group, content, picture, picture_name, title=None, parent_post=None, 
	assigned_to=None, status=None, event_datetime=None):
	
	access = get_access(group)
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

	access = get_access(post.doc.website_group)
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
	file_data = save_file(picture_name, picture, "Post", post.doc.name, decode=True)
	post.doc.picture_url = file_data.file_name or file_data.file_url
	webnotes.conn.set_value("Post", post.doc.name, "picture_url", post.doc.picture_url)
	clear_cache(website_group=post.doc.website_group)
	
@webnotes.whitelist()
def suggest_user(group, term):
	"""suggest a user that has read permission in this group tree"""
	profiles = webnotes.conn.sql("""select 
		pr.name, pr.first_name, pr.last_name, 
		pr.user_image, pr.fb_location, pr.fb_hometown
		from `tabProfile` pr
		where (pr.first_name like %(term)s or pr.last_name like %(term)s)
		and pr.name not in ("Guest", "Administrator") is not null and pr.enabled=1""", 
		{"term": "%{}%".format(term), "group": group}, as_dict=True)
	
	template = webnotes.get_template("templates/includes/profile_display.html")
	return [{
		"value": "{} {}".format(pr.first_name or "", pr.last_name or "").strip(), 
		"profile_html": template.render({"profile": pr}),
		"profile": pr.name
	} for pr in profiles]
