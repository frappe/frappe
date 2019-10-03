# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.core.doctype.notification_settings.notification_settings import (is_notifications_enabled,
	is_email_notifications_enabled)

class NotificationLog(Document):

	def after_insert(self):
		frappe.publish_realtime('notification', after_commit=True, user=self.user)
		if is_email_notifications_enabled(self.user):
			send_notification_email(self)


def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user

	return '''(`tabNotification Log`.user = '{user}')'''.format(user=user)

def create_notification_log(names, doc, email_content = None):
	doc = frappe._dict(doc)
	if(not isinstance(names, list)):
		if names:
			names = filter(None, names.split(', '))
	for name in names:
		user = name.strip()
		if frappe.db.exists('User', user):
			if is_notifications_enabled(user):
				from frappe.social.doctype.energy_point_settings.energy_point_settings import is_energy_point_enabled

				if doc.type == 'Energy Point' and not is_energy_point_enabled():
					return
				else:
					_doc = frappe.new_doc('Notification Log')
					_doc.type = doc.type
					_doc.user = user
					_doc.reference_doctype = doc.reference_doctype
					_doc.reference_name = doc.reference_name
					_doc.reference_user = doc.reference_user
					_doc.subject = doc.subject.replace('<div>', '').replace('</div>', '')
					_doc.email_content = email_content
					_doc.insert(ignore_permissions=True)

def send_notification_email(doc):
	from frappe.utils import get_url_to_form, strip_html, get_url

	doc_link = get_url_to_form(doc.reference_doctype, doc.reference_name)
	header = get_email_header(doc)
	email_subject = strip_html(doc.subject)

	try:
		frappe.sendmail(
			recipients = doc.user,
			sender = frappe.session.user,
			subject = email_subject,
			template = "new_notification",
			args = {
				"body_content": doc.subject,
				"description": doc.email_content,
				"doc_link": doc_link,
				"link": get_url()
			},
			header = [header, 'orange']
		)
	except:	
		pass



def get_email_header(doc):
	if doc.type == 'Mention' or doc.type == 'Assignment':
		return _('New {0}').format(doc.type)
	elif doc.type == 'Communication':
		return _('New Email')
	elif doc.type == 'Share':
		return _('New Document Shared')
	elif doc.type == 'Energy Point':
		return _('Energy Point Update')

@frappe.whitelist()
def set_notification_as_seen(notification_log):
	notification_log = frappe.parse_json(notification_log)
	for log in notification_log:
		frappe.db.set_value('Notification Log', log['name'], 'seen', 1, update_modified=False)

