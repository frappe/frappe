# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class PostComment(Document):
	def after_insert(self):
		frappe.publish_realtime('new_post_comment' + self.parent, self, after_commit=True)
