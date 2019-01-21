# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class DocumentFollow(Document):
	def before_insert(self):
		self.last_sent_on = frappe.utils.now_datetime()

