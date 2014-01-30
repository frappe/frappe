# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals

import webnotes
from webnotes.utils import get_fullname
from webnotes.utils.email_lib.bulk import send
from webnotes.utils.email_lib import sendmail

# TODO move these functions to framework
from aapkamanch.helpers import get_access
from aapkamanch.post import clear_post_cache
from aapkamanch.unit import clear_unit_views

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
		clear_unit_views(self.doc.unit)
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
	