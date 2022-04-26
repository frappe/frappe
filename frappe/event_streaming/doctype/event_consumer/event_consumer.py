# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import json
import os

import requests

import frappe
from frappe import _
from frappe.frappeclient import FrappeClient
from frappe.model.document import Document
from frappe.utils.background_jobs import get_jobs
from frappe.utils.data import get_url


class EventConsumer(Document):
	def validate(self):
		# approve subscribed doctypes for tests
		# frappe.flags.in_test won't work here as tests are running on the consumer site
		if os.environ.get("CI"):
			for entry in self.consumer_doctypes:
				entry.status = "Approved"

	def on_update(self):
		if not self.incoming_change:
			doc_before_save = self.get_doc_before_save()
			if doc_before_save.api_key != self.api_key or doc_before_save.api_secret != self.api_secret:
				return

			self.update_consumer_status()
		else:
			frappe.db.set_value(self.doctype, self.name, "incoming_change", 0)

		frappe.cache().delete_value("event_consumer_document_type_map")

	def on_trash(self):
		for i in frappe.get_all("Event Update Log Consumer", {"consumer": self.name}):
			frappe.delete_doc("Event Update Log Consumer", i.name)
		frappe.cache().delete_value("event_consumer_document_type_map")

	def update_consumer_status(self):
		consumer_site = get_consumer_site(self.callback_url)
		event_producer = consumer_site.get_doc("Event Producer", get_url())
		event_producer = frappe._dict(event_producer)
		config = event_producer.producer_doctypes
		event_producer.producer_doctypes = []
		for entry in config:
			if entry.get("has_mapping"):
				ref_doctype = consumer_site.get_value(
					"Document Type Mapping", "remote_doctype", entry.get("mapping")
				).get("remote_doctype")
			else:
				ref_doctype = entry.get("ref_doctype")

			entry["status"] = frappe.db.get_value(
				"Event Consumer Document Type", {"parent": self.name, "ref_doctype": ref_doctype}, "status"
			)

		event_producer.producer_doctypes = config
		# when producer doc is updated it updates the consumer doc
		# set flag to avoid deadlock
		event_producer.incoming_change = True
		consumer_site.update(event_producer)

	def get_consumer_status(self):
		response = requests.get(self.callback_url)
		if response.status_code != 200:
			return "offline"
		return "online"


@frappe.whitelist()
def register_consumer(data):
	"""create an event consumer document for registering a consumer"""
	data = json.loads(data)
	# to ensure that consumer is created only once
	if frappe.db.exists("Event Consumer", data["event_consumer"]):
		return None

	user = data["user"]
	if not frappe.db.exists("User", user):
		frappe.throw(_("User {0} not found on the producer site").format(user))

	if "System Manager" not in frappe.get_roles(user):
		frappe.throw(_("Event Subscriber has to be a System Manager."))

	consumer = frappe.new_doc("Event Consumer")
	consumer.callback_url = data["event_consumer"]
	consumer.user = data["user"]
	consumer.api_key = data["api_key"]
	consumer.api_secret = data["api_secret"]
	consumer.incoming_change = True
	consumer_doctypes = json.loads(data["consumer_doctypes"])

	for entry in consumer_doctypes:
		consumer.append(
			"consumer_doctypes",
			{"ref_doctype": entry.get("doctype"), "status": "Pending", "condition": entry.get("condition")},
		)

	consumer.insert()

	# consumer's 'last_update' field should point to the latest update
	# in producer's update log when subscribing
	# so that, updates after subscribing are consumed and not the old ones.
	last_update = str(get_last_update())
	return json.dumps({"last_update": last_update})


def get_consumer_site(consumer_url):
	"""create a FrappeClient object for event consumer site"""
	consumer_doc = frappe.get_doc("Event Consumer", consumer_url)
	consumer_site = FrappeClient(
		url=consumer_url,
		api_key=consumer_doc.api_key,
		api_secret=consumer_doc.get_password("api_secret"),
	)
	return consumer_site


def get_last_update():
	"""get the creation timestamp of last update consumed"""
	updates = frappe.get_list(
		"Event Update Log", "creation", ignore_permissions=True, limit=1, order_by="creation desc"
	)
	if updates:
		return updates[0].creation
	return frappe.utils.now_datetime()


@frappe.whitelist()
def notify_event_consumers(doctype):
	"""get all event consumers and set flag for notification status"""
	event_consumers = frappe.get_all(
		"Event Consumer Document Type", ["parent"], {"ref_doctype": doctype, "status": "Approved"}
	)
	for entry in event_consumers:
		consumer = frappe.get_doc("Event Consumer", entry.parent)
		consumer.flags.notified = False
		notify(consumer)


@frappe.whitelist()
def notify(consumer):
	"""notify individual event consumers about a new update"""
	consumer_status = consumer.get_consumer_status()
	if consumer_status == "online":
		try:
			client = get_consumer_site(consumer.callback_url)
			client.post_request(
				{
					"cmd": "frappe.event_streaming.doctype.event_producer.event_producer.new_event_notification",
					"producer_url": get_url(),
				}
			)
			consumer.flags.notified = True
		except Exception:
			consumer.flags.notified = False
	else:
		consumer.flags.notified = False

	# enqueue another job if the site was not notified
	if not consumer.flags.notified:
		enqueued_method = "frappe.event_streaming.doctype.event_consumer.event_consumer.notify"
		jobs = get_jobs()
		if not jobs or enqueued_method not in jobs[frappe.local.site] and not consumer.flags.notifed:
			frappe.enqueue(
				enqueued_method, queue="long", enqueue_after_commit=True, **{"consumer": consumer}
			)


def has_consumer_access(consumer, update_log):
	"""Checks if consumer has completely satisfied all the conditions on the doc"""

	if isinstance(consumer, str):
		consumer = frappe.get_doc("Event Consumer", consumer)

	if not frappe.db.exists(update_log.ref_doctype, update_log.docname):
		# Delete Log
		# Check if the last Update Log of this document was read by this consumer
		last_update_log = frappe.get_all(
			"Event Update Log",
			filters={
				"ref_doctype": update_log.ref_doctype,
				"docname": update_log.docname,
				"creation": ["<", update_log.creation],
			},
			order_by="creation desc",
			limit_page_length=1,
		)
		if not len(last_update_log):
			return False

		last_update_log = frappe.get_doc("Event Update Log", last_update_log[0].name)
		return len([x for x in last_update_log.consumers if x.consumer == consumer.name])

	doc = frappe.get_doc(update_log.ref_doctype, update_log.docname)
	try:
		for dt_entry in consumer.consumer_doctypes:
			if dt_entry.ref_doctype != update_log.ref_doctype:
				continue

			if not dt_entry.condition:
				return True

			condition: str = dt_entry.condition
			if condition.startswith("cmd:"):
				cmd = condition.split("cmd:")[1].strip()
				args = {"consumer": consumer, "doc": doc, "update_log": update_log}
				return frappe.call(cmd, **args)
			else:
				return frappe.safe_eval(condition, frappe._dict(doc=doc))
	except Exception as e:
		frappe.log_error(title="has_consumer_access error", message=e)
	return False
