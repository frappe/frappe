# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.core.doctype.notification_settings.notification_settings import (is_notifications_enabled,
	is_energy_point_notifications_enabled)

class NotificationLog(Document):

	def after_insert(self):
		frappe.publish_realtime('notification', after_commit=True, user=self.user)


def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user

	return '''(`tabNotification Log`.user = '{user}')'''.format(user=user)

def create_notification_log(names, doc):
	doc = frappe._dict(doc)
	if(not isinstance(names, list)):
		if names:
			names = filter(None, names.split(', '))
	for name in names:
		user = name.strip()
		if frappe.db.exists('User', user):
			if is_notifications_enabled(user):
				if doc.type == 'Energy Point' and not is_energy_point_notifications_enabled(user):
					return
				else:
					_doc = frappe.new_doc('Notification Log')
					_doc.type = doc.type
					_doc.user = name.strip()
					_doc.reference_doctype = doc.reference_doctype
					_doc.reference_name = doc.reference_name
					_doc.reference_user = doc.reference_user
					_doc.subject = doc.subject.replace('<div>', '').replace('</div>', '')
					_doc.insert(ignore_permissions=True)


@frappe.whitelist()
def set_notification_as_seen(notification_log):
	notification_log = frappe.parse_json(notification_log)
	for log in notification_log:
		frappe.db.set_value('Notification Log', log['name'], 'seen', 1, update_modified=False)

