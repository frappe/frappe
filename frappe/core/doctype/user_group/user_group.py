# -*- coding: utf-8 -*-
# Copyright (c) 2021, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
# import frappe
from frappe.model.document import Document
import frappe

class UserGroup(Document):
	def after_insert(self):
		frappe.publish_realtime('user_group_added', self.name)

	def on_trash(self):
		frappe.publish_realtime('user_group_deleted', self.name)
