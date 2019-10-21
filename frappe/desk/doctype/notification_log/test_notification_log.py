# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
from frappe.desk.form.assign_to import add as assign_task
import unittest

class TestNotificationLog(unittest.TestCase):
	def test_assignment(self):
		todo = self.get_todo()
		user = self.get_user()

		assign_task({
			"assign_to": user,
			"doctype": 'ToDo',
			"name": todo.name,
			"description": todo.description
		})
		log = self.get_last_notification_log()
		email = self.get_last_email_queue()
		self.assertEqual(log.type, 'Assignment')
		self.assertEqual(log.document_name, todo.name)

	def test_share(self):
		todo = self.get_todo()
		user = self.get_user()

		frappe.share.add('ToDo', todo.name, user)
		log = self.get_last_notification_log()
		self.assertEqual(log.type, 'Share')
		self.assertEqual(log.document_name, todo.name)

		email = self.get_last_email_queue()
		content = 'Subject: {} shared a document ToDo'.format(frappe.utils.get_fullname(frappe.session.user))
		self.assertTrue(content in email.message)


	def get_last_notification_log(self):
		res = frappe.db.get_all('Notification Log',
			fields=['type', 'document_name'],
			order_by='creation desc',
			limit=1
		)
		return res[0]

	def get_last_email_queue(self):
		res = frappe.db.get_all('Email Queue',
			fields=['message'],
			order_by='creation desc',
			limit=1
		)
		return res[0]

	def get_todo(self):
		if not frappe.get_all('ToDo'):
			return frappe.get_doc({ 'doctype': 'ToDo', 'description': 'Test for Notification' }).insert()

		res = frappe.get_all('ToDo', limit=1)
		return frappe.get_cached_doc('ToDo', res[0].name)

	def get_user(self):
		users = frappe.db.get_all('User', fields='name', limit=1)
		return users[0].name
