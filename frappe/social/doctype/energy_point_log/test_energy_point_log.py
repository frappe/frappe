# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
from .energy_point_log import create_energy_point_log

class TestEnergyPointLog(unittest.TestCase):
	def test_user_energy_point(self):
		frappe.set_user('test@example.com')
		todo_point_rule = create_energy_point_rule_for_todo()
		energy_point_of_user = frappe.get_value('User', 'test@example.com', 'energy_points')

		created_todo = create_a_todo()

		created_todo.status = 'Closed'
		created_todo.save()

		points_after_closing_todo = frappe.get_value('User', 'test@example.com', 'energy_points')

		self.assertEquals(points_after_closing_todo, energy_point_of_user + todo_point_rule.points)

		created_todo.save()
		points_after_double_save = frappe.get_value('User', 'test@example.com', 'energy_points')

		# point should not be awarded more than once for same doc
		self.assertEquals(points_after_double_save, energy_point_of_user + todo_point_rule.points)


def create_energy_point_rule_for_todo():
	point_rule = frappe.db.get_all(
		'Energy Point Rule',
		{'name':'ToDo closed'},
		['points', 'name'],
		limit=1
	)

	if point_rule: return point_rule[0]

	return frappe.get_doc({
		'doctype': 'Energy Point Rule',
		'rule_name': 'ToDo closed',
		'points': 5,
		'reference_doctype': 'ToDo',
		'condition': 'doc.status == "Closed"',
		'user_field': 'owner'
	}).insert(ignore_permissions=1)

def create_a_todo():
	return frappe.get_doc({
		'doctype': 'ToDo',
		'description': 'Fix a bug',
	})