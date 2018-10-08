# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class Post(Document):
	def on_update(self):
		if (self.get_doc_before_save().is_pinned != self.is_pinned):
			frappe.publish_realtime('toggle_pin' + self.name, self.is_pinned, after_commit=True)

	def after_insert(self):
		if self.reply_to:
			frappe.publish_realtime('new_post_reply' + self.reply_to, self, after_commit=True)
		else:
			frappe.publish_realtime('new_post', self.owner, after_commit=True)

@frappe.whitelist()
def toggle_like(post_name, user=None):
	liked_by = frappe.db.get_value('Post', post_name, 'liked_by')
	liked_by = liked_by.split('\n') if liked_by else []
	user = user or frappe.session.user

	if user in liked_by:
		liked_by.remove(user)
	else:
		liked_by.append(user)

	liked_by = '\n'.join(liked_by)
	frappe.db.set_value('Post', post_name, 'liked_by', liked_by)
	frappe.publish_realtime('update_liked_by' + post_name, liked_by, after_commit=True)

@frappe.whitelist()
def frequently_visited_links():
	return frappe.get_all('Route History', fields=['route', 'count(name) as count'], filters={
		'user': frappe.session.user
	}, group_by="route", order_by="count desc", limit=10)