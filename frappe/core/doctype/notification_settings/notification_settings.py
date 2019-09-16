# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class NotificationSettings(Document):
	def before_insert(self):
		if frappe.db.count('Notification Settings', {'user': frappe.session.user}) > 0:
			frappe.throw(_("Notification Settings already Exists"))

	def on_update(self):
		from frappe.desk.notifications import clear_notification_config
		clear_notification_config(frappe.session.user)


def is_notifications_enabled(user):
	if frappe.db.count('Notification Settings', {'user': user}) > 0:
		return frappe.get_cached_value('Notification Settings', {'user': user}, 'enable')
	else:
		return True

def is_email_notifications_enabled(user):
	if frappe.db.count('Notification Settings', {'user': user}) > 0:
		return frappe.get_cached_value('Notification Settings', {'user': user}, 'enable_email_notifications')
	else:
		return True

def is_energy_point_notifications_enabled(user):
	if frappe.db.count('Notification Settings', {'user': user}) > 0:
		return frappe.get_cached_value('Notification Settings', {'user': user}, 'enable_energy_point_notifications')
	else:
		return True

@frappe.whitelist()
def get_subscribed_documents():
	subscribed_documents = []
	settings = frappe.get_all('Notification Settings', {'user': frappe.session.user})
	if settings:
		name = settings[0].name
		doc = frappe.get_doc('Notification Settings', name)
		subscribed_documents = [item.document for item in doc.subscribed_documents]
	
	return subscribed_documents


def get_permission_query_conditions(user):
	if not user: user = frappe.session.user

	return '''(`tabNotification Settings`.user = '{user}')'''.format(user=user)