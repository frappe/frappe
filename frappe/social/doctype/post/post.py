# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class Post(Document):
	def after_insert(self):
		if self.reply_to:
			frappe.publish_realtime('new_post_reply', self, after_commit=True)
		else:
			frappe.publish_realtime('new_post', self, after_commit=True)
