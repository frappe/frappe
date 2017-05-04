# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

# test_records = frappe.get_test_records('Feedback Trigger')
def get_feedback_request(todo, feedback_trigger):
	return frappe.db.get_value("Feedback Request", {
		"is_sent": 1,
		"is_feedback_submitted": 0,
		"reference_doctype": "ToDo",
		"reference_name": todo,
		"feedback_trigger": feedback_trigger
	}, ["name", "key"])

class TestFeedbackTrigger(unittest.TestCase):
	def setUp(self):
		new_user = frappe.get_doc(dict(doctype='User', email='test-feedback@example.com',
			first_name='Tester')).insert(ignore_permissions=True)
		new_user.add_roles("System Manager")

	def tearDown(self):
		frappe.delete_doc("User", "test-feedback@example.com")
		frappe.delete_doc("Feedback Trigger", "ToDo")
		frappe.db.sql('delete from `tabEmail Queue`')
		frappe.db.sql('delete from `tabFeedback Request`')

	def test_feedback_trigger(self):
		""" Test feedback trigger """
		from frappe.www.feedback import accept

		frappe.delete_doc("Feedback Trigger", "ToDo")
		frappe.db.sql('delete from `tabEmail Queue`')
		frappe.db.sql('delete from `tabFeedback Request`')

		feedback_trigger = frappe.get_doc({
			"enabled": 1,
			"doctype": "Feedback Trigger",
			"document_type": "ToDo",
			"email_field": "assigned_by",
			"email_fieldname": "assigned_by",
			"subject": "{{ doc.name }} Task Completed",
			"condition": "doc.status == 'Closed'",
			"message": """Task {{ doc.name }} is Completed by {{ doc.owner }}.
			regarding the Task {{ doc.name }}"""
		}).insert(ignore_permissions=True)

		# create a todo
		todo = frappe.get_doc({
			"doctype": "ToDo",
			"owner": "test-feedback@example.com",
			"assigned_by": "test-feedback@example.com",
			"description": "Unable To Submit Sales Order #SO-00001"
		}).insert(ignore_permissions=True)

		# feedback alert mail should be sent only on 'Closed' status
		email_queue = frappe.db.sql("""select name from `tabEmail Queue` where
			reference_doctype='ToDo' and reference_name='{0}'""".format(todo.name))
		self.assertFalse(email_queue)

		# add a communication
		frappe.get_doc({
			"reference_doctype": "ToDo",
			"reference_name": todo.name,
			"communication_type": "Communication",
			"content": "Test Communication",
			"subject": "Test Communication",
			"doctype": "Communication"
		}).insert(ignore_permissions=True)

		# check if feedback mail alert is triggered
		todo.status = "Closed"
		todo.save(ignore_permissions=True)

		email_queue = frappe.db.sql("""select name from `tabEmail Queue` where
			reference_doctype='ToDo' and reference_name='{0}'""".format(todo.name))
		self.assertTrue(email_queue)

		# test if feedback is submitted for the todo
		feedback_request, request_key = get_feedback_request(todo.name, feedback_trigger.name)
		self.assertTrue(feedback_request)

		# test if mail alerts are triggered multiple times for same document
		todo.save(ignore_permissions=True)
		email_queue = frappe.db.sql("""select name from `tabEmail Queue` where
			reference_doctype='ToDo' and reference_name='{0}'""".format(todo.name))
		self.assertTrue(len(email_queue) == 1)
		frappe.db.sql('delete from `tabEmail Queue`')


		# Test if feedback is submitted sucessfully
		result = accept(request_key, "test-feedback@example.com", "ToDo", todo.name, "Great Work !!", 4, fullname="Test User")
		self.assertTrue(result)

		# test if feedback is saved in Communication
		docname = frappe.db.get_value("Communication", {
			"reference_doctype": "ToDo",
			"reference_name": todo.name,
			"communication_type": "Feedback",
			"feedback_request": feedback_request
		})

		communication = frappe.get_doc("Communication", docname)
		self.assertEqual(communication.rating, 4)
		self.assertEqual(communication.content, "Great Work !!")

		# test if link expired after feedback submission
		self.assertRaises(Exception, accept, key=request_key, sender="test-feedback@example.com",
			reference_doctype="ToDo", reference_name=todo.name, feedback="Thank You !!", rating=4, fullname="Test User")

		# auto feedback request should trigger only once
		todo.save(ignore_permissions=True)
		email_queue = frappe.db.sql("""select name from `tabEmail Queue` where
			reference_doctype='ToDo' and reference_name='{0}'""".format(todo.name))
		self.assertFalse(email_queue)
		frappe.delete_doc("ToDo", todo.name)

		# test if feedback requests and feedback communications are deleted?
		communications = frappe.get_all("Communication", {
			"reference_doctype": "ToDo",
			"reference_name": todo.name,
			"communication_type": "Feedback"
		})
		self.assertFalse(communications)
		
		feedback_requests = frappe.get_all("Feedback Request", {
			"reference_doctype": "ToDo",
			"reference_name": todo.name,
			"is_feedback_submitted": 0
		})
		self.assertFalse(feedback_requests)
		