# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import json

class ChatBot(Document):

	def validate(self):
		self.list_items = json.dumps(self.list_items)
		self.action = json.dumps(self.action)
		self.info = json.dumps(self.info)
