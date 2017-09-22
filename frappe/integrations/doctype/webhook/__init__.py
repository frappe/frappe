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
		webhooks = frappe.cache().get_value('webhooks')
		if webhooks==None:
			webhooks_list = frappe.get_all('Webhook',
				fields=["name", "webhook_docevent", "webhook_doctype"])

			webhooks = {}
			for w in webhooks_list:
				webhooks.setdefault(w.webhook_doctype, []).append(w)
			frappe.cache().set_value('webhooks', webhooks)
		doc.flags.webhooks = webhooks.get(doc.doctype, None)

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
		if event and webhook.webhook_docevent == event:
			_webhook_request(webhook)
