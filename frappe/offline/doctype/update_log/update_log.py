# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe.model.document import Document
from frappe.utils.background_jobs import get_jobs

class UpdateLog(Document):
	def validate(self):
		'''Sync master data to followers whenever update log is generated'''
		enqueued_method = 'frappe.offline.doctype.node_configuration.node_configuration.sync_master_data'
		jobs = get_jobs()
		if not jobs or enqueued_method not in jobs[frappe.local.site]:
			frappe.enqueue(enqueued_method, queue = 'default')
