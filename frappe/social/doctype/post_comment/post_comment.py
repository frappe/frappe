# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.core.doctype.user.user import extract_mentions

class PostComment(Document):
	def after_insert(self):
		mentions = extract_mentions(self.content)
		for mention in mentions:
			frappe.publish_realtime('mention', "Someone mentioned you", user=mention, after_commit=True)
		frappe.publish_realtime('new_post_comment' + self.parent, self, after_commit=True)
