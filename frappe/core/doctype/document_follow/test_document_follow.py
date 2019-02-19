# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
import frappe.desk.form.doc_subscription as doc_subscription

class TestDocumentFollow(unittest.TestCase):

	def test_add_subscription(self):
		user = get_user()
		event_doc = get_event()
		doc = doc_subscription.add_subcription("Event", event_doc.name , user.name)
		self.assertEquals(doc.user, user.name)

	def test_get_version(self):
		event_doc = get_event()
		event_doc.description = "This is a test description"
		event_doc.save()
		version_document= doc_subscription.get_version("Event", event_doc.name, "Hourly")
		self.assertEquals(version_document[0]['doc_name'],event_doc.name)

	def test_get_comments(self):
		event_doc = get_event()
		event_doc.add_comment("Comment", "Test Comment for testing")
		comments = doc_subscription.get_comments("Event", event_doc.name, "Hourly")
		self.assertEquals(comments[0]['doc_name'],event_doc.name)


	def tearDown(self):
		frappe.db.rollback()

def get_event():
	doc = frappe.new_doc("Event")
	doc.subject = "_Test_Doc_Follow"
	doc.starts_on = frappe.utils.now()
	doc.ends_on = frappe.utils.add_days(frappe.utils.now(),5)
	doc.description = "Hello"
	doc.insert()
	return doc

def get_user():
	doc = frappe.new_doc("User")
	doc.email = "test@docsub.com"
	doc.first_name = "Test"
	doc.last_name = "User"
	doc.send_welcome_email = 0
	doc.enable_email_for_follow_documents = 1
	doc.frequency_for_follow_documents_email = "Hourly"
	doc.insert()
	return doc


