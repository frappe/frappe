# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class ChatMessage(Document):
	def on_update(self):
		frappe.publish_realtime('chat:message', dict(
			room = self.room,
			content = self.message_content
		), after_commit = True)


@frappe.whitelist()
def send(room, message):
	# room = frappe.get_doc('Chat Room', room)
	doc = frappe.new_doc('Chat Message')
	doc.room = room
	doc.message_content = message
	
	doc.insert()

