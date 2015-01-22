# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.utils import get_fullname
from frappe.utils.email_lib.bulk import send
from frappe.utils.email_lib import sendmail

from frappe.model.document import Document

class Post(Document):

	def validate(self):
		if not self.parent_post and not self.title:
			frappe.throw(_("Title is required"))

		self.assigned_to = frappe.db.get_value(self.doctype, self.name, "assigned_to")
		if self.is_task:
			if not self.status:
				self.status = "Open"
			if self.assigned_to:
				if not self.assigned_to_fullname:
					self.assigned_to_fullname = get_fullname(self.assigned_to)
			else:
				self.assigned_to_fullname = None
		else:
			self.assigned_to = self.assigned_to_fullname = self.status = None

		if self.is_event:
			if not self.event_datetime:
				frappe.throw(_("Please specify Event date and time"))
		else:
			self.event_datetime = None

	def on_update(self):
		from frappe.templates.website_group.post import clear_post_cache
		from frappe.website.doctype.website_group.website_group import clear_cache

		clear_cache(website_group=self.website_group)
		clear_post_cache(self.parent_post or self.name)

		if self.assigned_to and self.assigned_to != self.assigned_to \
			and frappe.session.user != self.assigned_to:

			# send assignment email
			sendmail(recipients=[self.assigned_to],
				subject="You have been assigned this Task by {}".format(get_fullname(self.modified_by)),
				msg=self.get_reply_email_message(self.name, get_fullname(self.owner)))

	def send_email_on_reply(self):
		owner_fullname = get_fullname(self.owner)

		parent_post = frappe.get_doc("Post", self.parent_post)

		message = self.get_reply_email_message(self.name, owner_fullname)

		# send email to the owner of the post, if he/she is different
		if parent_post.owner != self.owner:
			send(recipients=[parent_post.owner],
				subject="{someone} replied to your post".format(someone=owner_fullname),
				message=message,

				# to allow unsubscribe
				doctype='Post',
				email_field='owner',

				# for tracking sent status
				ref_doctype=self.doctype, ref_docname=self.name)

		# send email to members who part of the conversation
		participants = frappe.db.sql("""select owner, name from `tabPost`
			where parent_post=%s and owner not in (%s, %s) order by creation asc""",
			(self.parent_post, parent_post.owner, self.owner), as_dict=True)

		send(recipients=[p.owner for p in participants],
			subject="{someone} replied to a post by {other}".format(someone=owner_fullname,
				other=get_fullname(parent_post.owner)),
			message=message,

			# to allow unsubscribe
			doctype='Post',
			email_field='owner',

			# for tracking sent status
			ref_doctype=self.doctype, ref_docname=self.name)

	def get_reply_email_message(self, post_name, owner_fullname=None):
		message = self.content
		if self.picture_url:
			message += """<div><img src="{url}" style="max-width: 100%"></div>"""\
				.format(url=self.picture_url)
		message += "<p>By {fullname}</p>".format(fullname=owner_fullname)
		message += "<p><a href='/post/{post_name}'>Click here to view the post</a></p>".format(fullname=owner_fullname,
			post_name=post_name)
		return message
