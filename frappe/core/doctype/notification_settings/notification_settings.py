# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class NotificationSettings(Document):
	pass
	# def validate(self):
	# 	create_notification_settings()

def is_notifications_enabled():
	return frappe.get_cached_value('Notification Settings', None, 'enable')

def is_energy_point_notifications_enabled():
	return frappe.get_cached_value('Notification Settings', None, 'enable_energy_point_notifications')

@frappe.whitelist()
def create_notification_settings():
	_doc = frappe.new_doc('Notification Settings')
	_doc.insert(ignore_permissions=True)