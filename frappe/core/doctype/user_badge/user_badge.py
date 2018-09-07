# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class UserBadge(Document):
	def after_insert(self):
		frappe.msgprint('Heyy! You got {} badge'.format(self.badge), 'hello')
