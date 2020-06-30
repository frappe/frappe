# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.desk.doctype.notification_settings.notification_settings import (is_notifications_enabled, is_email_notifications_enabled_for_type, set_seen_value)

class NotificationLog(Document):
	def after_insert(self):
		frappe.publish_realtime('notification', after_commit=True, user=self.for_user)
		set_notifications_as_unseen(self.for_user)
		if is_email_notifications_enabled_for_type(self.for_user, self.type):
			send_notification_email(self)


def get_permission_query_conditions(for_user):
	if not for_user:
		for_user = frappe.session.user

	if for_user == 'Administrator':
		return

	return '''(`tabNotification Log`.for_user = '{user}')'''.format(user=for_user)

def get_title(doctype, docname, title_field=None):
	if not title_field:
		title_field = frappe.get_meta(doctype).get_title_field()
	title = docname if title_field == "name" else \
		frappe.db.get_value(doctype, docname, title_field)
	return title

def get_title_html(title):
	return '<b class="subject-title">{0}</b>'.format(title)

def enqueue_create_notification(users, doc):
	'''
	During installation of new site, enqueue_create_notification tries to connect to Redis.
	This breaks new site creation if Redis server is not running.
	We do not need any notifications in fresh installation
	'''
	if frappe.flags.in_install:
		return

	doc = frappe._dict(doc)

	if isinstance(users, frappe.string_types):
		users = [user.strip() for user in users.split(',') if user.strip()]
	users = list(set(users))

	frappe.enqueue(
		'frappe.desk.doctype.notification_log.notification_log.make_notification_logs',
		doc=doc,
		users=users,
		now=frappe.flags.in_test
	)

def make_notification_logs(doc, users):
	from frappe.social.doctype.energy_point_settings.energy_point_settings import is_energy_point_enabled

	for user in users:
		if frappe.db.exists('User', user):
			if is_notifications_enabled(user):
				if doc.type == 'Energy Point' and not is_energy_point_enabled():
					return

				_doc = frappe.new_doc('Notification Log')
				_doc.update(doc)
				_doc.for_user = user
				_doc.subject = _doc.subject.replace('<div>', '').replace('</div>', '')
				if _doc.for_user != _doc.from_user or doc.type == 'Energy Point' or doc.type == 'Alert':
					_doc.insert(ignore_permissions=True)

def send_notification_email(doc):

	if doc.type == 'Energy Point' and doc.email_content is None:
		return

	from frappe.utils import get_url_to_form, strip_html

	doc_link = get_url_to_form(doc.document_type, doc.document_name)
	header = get_email_header(doc)
	email_subject = strip_html(doc.subject)

	frappe.sendmail(
		recipients = doc.for_user,
		subject = email_subject,
		template = "new_notification",
		args = {
			'body_content': doc.subject,
			'description': doc.email_content,
			'document_type': doc.document_type,
			'document_name': doc.document_name,
			'doc_link': doc_link
		},
		header = [header, 'orange'],
		now=frappe.flags.in_test
	)

def get_email_header(doc):
	docname = doc.document_name
	header_map = {
		'Default': _('New Notification'),
		'Mention': _('New Mention on {0}').format(docname),
		'Assignment': _('Assignment Update on {0}').format(docname),
		'Share': _('New Document Shared {0}').format(docname),
		'Energy Point': _('Energy Point Update on {0}').format(docname),
	}

	return header_map[doc.type or 'Default']

@frappe.whitelist()
def mark_all_as_read():
	unread_docs_list = frappe.db.get_all('Notification Log', filters = {'read': 0, 'for_user': frappe.session.user})
	unread_docnames = [doc.name for doc in unread_docs_list]
	if unread_docnames:
		filters = {'name': ['in', unread_docnames]}
		frappe.db.set_value('Notification Log', filters, 'read', 1, update_modified=False)


@frappe.whitelist()
def mark_as_read(docname):
	if docname:
		frappe.db.set_value('Notification Log', docname, 'read', 1, update_modified=False)

@frappe.whitelist()
def trigger_indicator_hide():
	frappe.publish_realtime('indicator_hide', user=frappe.session.user)

def set_notifications_as_unseen(user):
	try:
		frappe.db.set_value('Notification Settings', user, 'seen', 0)
	except frappe.DoesNotExistError:
		return
