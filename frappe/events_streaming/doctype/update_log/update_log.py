# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests
from frappe.model.document import Document
from frappe.utils.background_jobs import get_jobs

class UpdateLog(Document):
	def after_insert(self):
		'''Send update notification updates to event consumers whenever update log is generated'''
		enqueued_method = 'frappe.events_streaming.doctype.event_consumer.event_consumer.notify_event_consumers'
		jobs = get_jobs()
		if not jobs or enqueued_method not in jobs[frappe.local.site]:
			frappe.enqueue(enqueued_method, queue = 'default', enqueue_after_commit = True)