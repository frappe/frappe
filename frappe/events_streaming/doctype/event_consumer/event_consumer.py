# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests
import time
import json
from frappe.model.document import Document
from frappe.frappeclient import FrappeClient

class EventConsumer(Document):
	pass

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
	return (api_key, api_secret)