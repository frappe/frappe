# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import json

class ChatMessage(Document):
	
	def validate(self):
		self.chat_data = json.dumps(self.chat_data)
		self.bot_data = json.dumps(self.bot_data)
