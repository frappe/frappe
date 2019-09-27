# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
from frappe.utils import random_string
from frappe.test_runner import make_test_records

class TestAutoAssign(unittest.TestCase):
	def setUp(self):
		make_test_records("User")
		days = [
			dict(day = 'Sunday'),
			dict(day = 'Monday'),
			dict(day = 'Tuesday'),
			dict(day = 'Wednesday'),
			dict(day = 'Thursday'),
			dict(day = 'Friday'),
			dict(day = 'Saturday'),
		]
		self.assignment_rule = get_assignment_rule([days, days])
		clear_assignments()

	def test_round_robin(self):
		note = make_note(dict(public=1))

		# check if auto assigned to first user
		self.assertEqual(frappe.db.get_value('ToDo', dict(
			reference_type = 'Note',
			reference_name = note.name,
			status = 'Open'
		), 'owner'), 'test@example.com')

		note = make_note(dict(public=1))

		# check if auto assigned to second user
		self.assertEqual(frappe.db.get_value('ToDo', dict(
			reference_type = 'Note',
			reference_name = note.name,
			status = 'Open'
		), 'owner'), 'test1@example.com')

		clear_assignments()

		note = make_note(dict(public=1))

		# check if auto assigned to third user, even if
		# previous assignments where closed
		self.assertEqual(frappe.db.get_value('ToDo', dict(
			reference_type = 'Note',
			reference_name = note.name,
			status = 'Open'
		), 'owner'), 'test2@example.com')

		# check loop back to first user
		note = make_note(dict(public=1))

		self.assertEqual(frappe.db.get_value('ToDo', dict(
			reference_type = 'Note',
			reference_name = note.name,
			status = 'Open'
		), 'owner'), 'test@example.com')

	def test_load_balancing(self):
		self.assignment_rule.rule = 'Load Balancing'
		self.assignment_rule.save()

		for _ in range(30):
			note = make_note(dict(public=1))

		# check if each user has 10 assignments (?)
		for user in ('test@example.com', 'test1@example.com', 'test2@example.com'):
			self.assertEqual(len(frappe.get_all('ToDo', dict(owner = user, reference_type = 'Note'))), 10)

		# clear 5 assignments for first user
		# can't do a limit in "delete" since postgres does not support it
		for d in frappe.get_all('ToDo', dict(reference_type = 'Note', owner = 'test@example.com'), limit=5):
			frappe.db.sql("delete from tabToDo where name = %s", d.name)

		# add 5 more assignments
		for i in range(5):
			make_note(dict(public=1))

		# check if each user still has 10 assignments
		for user in ('test@example.com', 'test1@example.com', 'test2@example.com'):
			self.assertEqual(len(frappe.get_all('ToDo', dict(owner = user, reference_type = 'Note'))), 10)


	def test_assign_condition(self):
		# check condition
		note = make_note(dict(public=0))

		self.assertEqual(frappe.db.get_value('ToDo', dict(
			reference_type = 'Note',
			reference_name = note.name,
			status = 'Open'
		), 'owner'), None)

	def test_clear_assignment(self):
		note = make_note(dict(public=1))

		# check if auto assigned to first user
		todo = frappe.get_list('ToDo', dict(
			reference_type = 'Note',
			reference_name = note.name,
			status = 'Open'
		))[0]

		todo = frappe.get_doc('ToDo', todo['name'])
		self.assertEqual(todo.owner, 'test@example.com')

		# test auto unassign
		note.public = 0
		note.save()

		todo.load_from_db()

		# check if todo is cancelled
		self.assertEqual(todo.status, 'Cancelled')

	def test_close_assignment(self):
		note = make_note(dict(public=1, content="valid"))

		# check if auto assigned
		todo = frappe.get_list('ToDo', dict(
			reference_type = 'Note',
			reference_name = note.name,
			status = 'Open'
		))[0]

		todo = frappe.get_doc('ToDo', todo['name'])
		self.assertEqual(todo.owner, 'test@example.com')

		note.content="Closed"
		note.save()

		todo.load_from_db()

		# check if todo is closed
		self.assertEqual(todo.status, 'Closed')
		# check if closed todo retained assignment
		self.assertEqual(todo.owner, 'test@example.com')

	def check_multiple_rules(self):
		note = make_note(dict(public=1, notify_on_login=1))

		# check if auto assigned to test3 (2nd rule is applied, as it has higher priority)
		self.assertEqual(frappe.db.get_value('ToDo', dict(
			reference_type = 'Note',
			reference_name = note.name,
			status = 'Open'
		), 'owner'), 'test@example.com')

	def check_assignment_rule_scheduling(self):
		frappe.db.sql("DELETE FROM `tabAssignment Rule`")

		days_1 = [dict(day = 'Sunday'), dict(day = 'Monday'), dict(day = 'Tuesday')]

		days_2 = [dict(day = 'Wednesday'), dict(day = 'Thursday'), dict(day = 'Friday'), dict(day = 'Saturday')]

		get_assignment_rule([days_1, days_2], ['public == 1', 'public == 1'])

		frappe.flags.assignment_day = "Monday"
		note = make_note(dict(public=1))

		self.assertIn(frappe.db.get_value('ToDo', dict(
			reference_type = 'Note',
			reference_name = note.name,
			status = 'Open'
		), 'owner'), ['test@example.com', 'test1@example.com', 'test2@example.com'])

		frappe.flags.assignment_day = "Friday"
		note = make_note(dict(public=1))

		self.assertIn(frappe.db.get_value('ToDo', dict(
			reference_type = 'Note',
			reference_name = note.name,
			status = 'Open'
		), 'owner'), ['test3@example.com'])

def clear_assignments():
	frappe.db.sql("delete from tabToDo where reference_type = 'Note'")

def get_assignment_rule(days, assign=None):
	frappe.delete_doc_if_exists('Assignment Rule', 'For Note 1')

	if not assign:
		assign = ['public == 1', 'notify_on_login == 1']

	assignment_rule = frappe.get_doc(dict(
		name = 'For Note 1',
		doctype = 'Assignment Rule',
		priority = 0,
		document_type = 'Note',
		assign_condition = assign[0],
		unassign_condition = 'public == 0 or notify_on_login == 1',
		close_condition = '"Closed" in content',
		rule = 'Round Robin',
		assignment_days = days[0],
		users = [
			dict(user = 'test@example.com'),
			dict(user = 'test1@example.com'),
			dict(user = 'test2@example.com'),
		]
	)).insert()

	frappe.delete_doc_if_exists('Assignment Rule', 'For Note 2')

	# 2nd rule
	frappe.get_doc(dict(
		name = 'For Note 2',
		doctype = 'Assignment Rule',
		priority = 1,
		document_type = 'Note',
		assign_condition = assign[1],
		unassign_condition = 'notify_on_login == 0',
		rule = 'Round Robin',
		assignment_days =  days[1],
		users = [
			dict(user = 'test3@example.com')
		]
	)).insert()

	return assignment_rule

def make_note(values=None):
	note = frappe.get_doc(dict(
		doctype = 'Note',
		title = random_string(10),
		content = random_string(20)
	))

	if values:
		note.update(values)

	note.insert()

	return note