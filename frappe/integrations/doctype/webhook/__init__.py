# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe

def run_webhooks(doc, method):
	'''Run webhooks for this method'''
	if frappe.flags.in_import or frappe.flags.in_patch or frappe.flags.in_install:
		return

	if not getattr(frappe.local, 'webhooks_executed', None):
		frappe.local.webhooks_executed = []

	if doc.flags.webhooks == None:
		webhooks = frappe.cache().hget('webhooks', doc.doctype)
		if webhooks==None:
			webhooks = frappe.get_all('Webhook',
				fields=["name", "webhook_docevent", "webhook_doctype"])
			frappe.cache().hset('webhooks', doc.doctype, webhooks)
		doc.flags.webhooks = webhooks

	if not doc.flags.webhooks:
		return

	def _webhook_request(webhook):
		if not webhook.name in frappe.local.webhooks_executed:
			frappe.enqueue("frappe.integrations.doctype.webhook.webhook.enqueue_webhook", doc=doc, webhook=webhook)
			frappe.local.webhooks_executed.append(webhook.name)

	event_list = ["on_update", "after_insert", "on_submit", "on_cancel", "on_trash"]

	if not doc.flags.in_insert:
		# value change is not applicable in insert
		event_list.append('on_change')
		event_list.append('before_update_after_submit')

	for webhook in doc.flags.webhooks:
		event = method if method in event_list else None
		if event and webhook.webhook_docevent == event and webhook.webhook_doctype == doc.doctype:
			_webhook_request(webhook)
