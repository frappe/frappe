# Copyright (c) 2017, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe


def get_all_webhooks():
	# query webhooks
	webhooks_list = frappe.get_all(
		"Webhook",
		fields=["name", "condition", "webhook_docevent", "webhook_doctype"],
		filters={"enabled": True},
	)

	# make webhooks map
	webhooks = {}
	for w in webhooks_list:
		webhooks.setdefault(w.webhook_doctype, []).append(w)

	return webhooks


def run_webhooks(doc, method):
	"""Run webhooks for this method"""

	frappe_flags = frappe.local.flags

	if (
		frappe_flags.in_import
		or frappe_flags.in_patch
		or frappe_flags.in_install
		or frappe_flags.in_migrate
	):
		return

	if frappe_flags.webhooks_executed is None:
		frappe_flags.webhooks_executed = {}

	# load all webhooks from cache / DB
	webhooks = frappe.cache().get_value("webhooks", get_all_webhooks)

	# get webhooks for this doctype
	webhooks_for_doc = webhooks.get(doc.doctype, None)

	if not webhooks_for_doc:
		# no webhooks, quit
		return

	def _webhook_request(webhook):
		if webhook.name not in frappe_flags.webhooks_executed.get(doc.name, []):
			frappe.enqueue(
				"frappe.integrations.doctype.webhook.webhook.enqueue_webhook",
				enqueue_after_commit=True,
				doc=doc,
				webhook=webhook,
			)

			# keep list of webhooks executed for this doc in this request
			# so that we don't run the same webhook for the same document multiple times
			# in one request
			frappe_flags.webhooks_executed.setdefault(doc.name, []).append(webhook.name)

	event_list = ["on_update", "after_insert", "on_submit", "on_cancel", "on_trash"]

	if not doc.flags.in_insert:
		# value change is not applicable in insert
		event_list.append("on_change")
		event_list.append("before_update_after_submit")

	from frappe.integrations.doctype.webhook.webhook import get_context

	for webhook in webhooks_for_doc:
		trigger_webhook = False
		event = method if method in event_list else None
		if not webhook.condition:
			trigger_webhook = True
		elif frappe.safe_eval(webhook.condition, eval_locals=get_context(doc)):
			trigger_webhook = True

		if trigger_webhook and event and webhook.webhook_docevent == event:
			_webhook_request(webhook)
