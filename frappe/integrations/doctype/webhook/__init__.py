# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def run_webhooks(doc, method):
	'''Run webhooks for this method'''
	if frappe.flags.in_import or frappe.flags.in_patch or frappe.flags.in_install:
		return

	if frappe.flags.webhooks_executed is None:
		frappe.flags.webhooks_executed = {}

	if frappe.flags.webhooks == None:
		# load webhooks from cache
		webhooks = frappe.cache().get_value('webhooks')
		if webhooks==None:
			# query webhooks
			webhooks_list = frappe.get_all('Webhook',
				fields=["name", "webhook_docevent", "webhook_doctype"])

			# make webhooks map for cache
			webhooks = {}
			for w in webhooks_list:
				webhooks.setdefault(w.webhook_doctype, []).append(w)
			frappe.cache().set_value('webhooks', webhooks)

		frappe.flags.webhooks = webhooks

	# get webhooks for this doctype
	webhooks_for_doc = frappe.flags.webhooks.get(doc.doctype, None)

	if not webhooks_for_doc:
		# no webhooks, quit
		return

	def _webhook_request(webhook):
		if not webhook.name in frappe.flags.webhooks_executed.get(doc.name, []):
			frappe.enqueue("frappe.integrations.doctype.webhook.webhook.enqueue_webhook",
				enqueue_after_commit=True, doc=doc, webhook=webhook)

			# keep list of webhooks executed for this doc in this request
			# so that we don't run the same webhook for the same document multiple times
			# in one request
			frappe.flags.webhooks_executed.setdefault(doc.name, []).append(webhook.name)

	event_list = ["on_update", "after_insert", "on_submit", "on_cancel", "on_trash"]

	if not doc.flags.in_insert:
		# value change is not applicable in insert
		event_list.append('on_change')
		event_list.append('before_update_after_submit')

	for webhook in webhooks_for_doc:
		event = method if method in event_list else None
		if event and webhook.webhook_docevent == event:
			_webhook_request(webhook)
