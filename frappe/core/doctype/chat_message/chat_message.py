# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import json
from frappe import _

class ChatMessage(Document):
	
	def validate(self):
		try:
			json.loads(self.chat_data)
		except Exception, e:
			frappe.throw(_('Please check the Chat data field before saving.'))
		try:
			json.loads(self.bot_data)
		except Exception, e:
			frappe.throw(_('Please check the Bot data field before saving.'))