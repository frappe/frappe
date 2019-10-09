# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.desk.doctype.notification_settings.notification_settings import (is_notifications_enabled,
	is_email_notifications_enabled, is_email_notifications_enabled_for_type)

class NotificationLog(Document):

	def after_insert(self):
		frappe.publish_realtime('notification', after_commit=True, user=self.for_user)
		if is_email_notifications_enabled(self.for_user):
			send_notification_email(self)


def get_permission_query_conditions(for_user):
	if not for_user:
		for_user = frappe.session.user
	
	if for_user == 'Administrator':
		return

	return '''(`tabNotification Log`.for_user = '{user}')'''.format(user=for_user)

def create_notification(names, doc, email_content = None):
	doc = frappe._dict(doc)
	if not isinstance(names, list):
		if names:
			names = filter(None, names.split(', '))
	for name in names:
		user = name.strip()
		if frappe.db.exists('User', user):
			if is_notifications_enabled(user):
				frappe.enqueue(
					'frappe.desk.doctype.notification_log.notification_log.make_notification_log',
					doc = doc,
					user = user,
					email_content = email_content
				)

def make_notification_log(doc, user, email_content):
	from frappe.social.doctype.energy_point_settings.energy_point_settings import is_energy_point_enabled
	if doc.type == 'Energy Point' and not is_energy_point_enabled():
		return
	else:
		_doc = frappe.new_doc('Notification Log')
		_doc.type = doc.type
		_doc.for_user = user
		_doc.document_type = doc.document_type
		_doc.document_name = doc.document_name
		_doc.from_user = doc.reference_user
		_doc.subject = doc.subject.replace('<div>', '').replace('</div>', '')
		_doc.email_content = email_content
		_doc.insert(ignore_permissions=True)

def send_notification_email(doc):
	is_type_enabled = is_email_notifications_enabled_for_type(doc.for_user, doc.type)
	if not is_type_enabled:
		return

	from frappe.utils import get_url_to_form, strip_html, get_url

	doc_link = get_url_to_form(doc.document_type, doc.document_name)
	header = get_email_header(doc)
	email_subject = strip_html(doc.subject)

	try:
		frappe.sendmail(
			recipients = doc.for_user,
			sender = frappe.session.user,
			subject = email_subject,
			template = "new_notification",
			args = {
				'body_content': doc.subject,
				'description': doc.email_content,
				'document_type': doc.document_type,
				'document_name': doc.document_name,
				"doc_link": doc_link
			},
			header = [header, 'orange']
		)
	except Exception:
		pass

def get_email_header(doc):
	if doc.type == 'Mention' or doc.type == 'Assignment':
		return _('New {0}').format(doc.type)
	elif doc.type == 'Share':
		return _('New Document Shared')
	elif doc.type == 'Energy Point':
		return _('Energy Point Update')

@frappe.whitelist()
def mark_as_seen(docnames):
	docnames = frappe.parse_json(docnames)
	if docnames:
		filters = {'name': ['in', docnames]}
		frappe.db.set_value('Notification Log', filters, 'seen', 1, update_modified=False)
