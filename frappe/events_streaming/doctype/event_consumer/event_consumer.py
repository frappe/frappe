# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import time
import json
from frappe.model.document import Document
from frappe.frappeclient import FrappeClient
from frappe.events_streaming.doctype.event_producer.event_producer import get_current_node

class EventConsumer(Document):
	def notify(self):
		client = get_consumer_site(self.callback_url)
		response = client.post_request({
			'cmd': 'frappe.events_streaming.doctype.event_producer.event_producer.new_event_notification',
			'producer_url': get_current_node()
		})

@frappe.whitelist(allow_guest=True)
def register_consumer(event_consumer, subscribed_doctypes, user):
	consumer = frappe.new_doc('Event Consumer')
	consumer.callback_url = event_consumer
	consumer.user = user
	subscribed_doctypes = json.loads(subscribed_doctypes)

	for entry in subscribed_doctypes:
		consumer.append('subscribed_doctypes',{
			'ref_doctype': entry
		})

	api_key = frappe.generate_hash(length=10)
	api_secret = frappe.generate_hash(length=10)
	consumer.api_key = api_key
	consumer.api_secret = api_secret
	consumer.insert(ignore_permissions = True)

	# consumer's 'last_update' field should point to the latest update in producer's update log when subscribing
	# so that, updates after subscribing are consumed and not the old ones.
	last_update = get_last_update()

	return (api_key, api_secret, last_update)

@frappe.whitelist()
def notify_event_consumers():
	event_consumers = frappe.get_all('Event Consumer')
	for event_consumer in event_consumers:
		consumer = frappe.get_doc('Event Consumer', event_consumer.name)
		consumer.notify()

def get_consumer_site(consumer_url):
	consumer_doc = frappe.get_doc('Event Consumer', consumer_url)
	consumer_site = FrappeClient(
		url=consumer_url,
		api_key=consumer_doc.api_key,
		api_secret=consumer_doc.get_password('api_secret'),
		frappe_authorization_source='Event Producer'
	)
	return consumer_site

@frappe.whitelist()
def get_last_update():
	last_updates = frappe.get_list('Update Log', ignore_permissions=True)
	return last_updates[0].name