# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
from .energy_point_log import get_energy_points
from frappe.utils.testutils import add_custom_field, clear_custom_fields

class TestEnergyPointLog(unittest.TestCase):
	def tearDown(self):
		frappe.db.sql('DELETE FROM `tabEnergy Point Log`')
		frappe.db.sql('DELETE FROM `tabEnergy Point Rule`')

	def test_user_energy_point(self):
		frappe.set_user('test@example.com')
		todo_point_rule = create_energy_point_rule_for_todo()
		energy_point_of_user = get_energy_points('test@example.com')

		created_todo = create_a_todo()

		created_todo.status = 'Closed'
		created_todo.save()

		points_after_closing_todo = get_energy_points('test@example.com')

		self.assertEquals(points_after_closing_todo, energy_point_of_user + todo_point_rule.points)

		created_todo.save()
		points_after_double_save = get_energy_points('test@example.com')

		# point should not be awarded more than once for same doc
		self.assertEquals(points_after_double_save, energy_point_of_user + todo_point_rule.points)

	def test_points_based_on_multiplier_field(self):
		frappe.set_user('test@example.com')
		add_custom_field('ToDo', 'multiplier', 'Int')
		multiplier_value = 2

		todo_point_rule = create_energy_point_rule_for_todo('multiplier')
		energy_point_of_user = get_energy_points('test@example.com')

		created_todo = create_a_todo()
		points_after_closing_todo = get_energy_points('test@example.com')
		created_todo.status = 'Closed'
		created_todo.multiplier = multiplier_value
		created_todo.save()

		points_after_closing_todo = get_energy_points('test@example.com')

		self.assertEquals(points_after_closing_todo, energy_point_of_user + (todo_point_rule.points * multiplier_value))
		clear_custom_fields('ToDo')

	def test_disabled_energy_points(self):
		settings = frappe.get_single('Energy Point Settings')
		settings.enabled = 0
		settings.save()

		frappe.set_user('test@example.com')
		create_energy_point_rule_for_todo()
		energy_point_of_user = get_energy_points('test@example.com')

		created_todo = create_a_todo()

		created_todo.status = 'Closed'
		created_todo.save()

		points_after_closing_todo = get_energy_points('test@example.com')

		# no change in points
		self.assertEquals(points_after_closing_todo, energy_point_of_user)

		settings.enabled = 1
		settings.save()

def create_energy_point_rule_for_todo(multiplier_field=None):
	name = 'ToDo Closed'
	point_rule = frappe.db.get_all(
		'Energy Point Rule',
		{'name': name},
		['*'],
		limit=1
	)

	if point_rule: return point_rule[0]

	return frappe.get_doc({
		'doctype': 'Energy Point Rule',
		'rule_name': name,
		'points': 5,
		'reference_doctype': 'ToDo',
		'condition': 'doc.status == "Closed"',
		'user_field': 'owner',
		'multiplier_field': multiplier_field
	}).insert(ignore_permissions=1)

def create_a_todo():
	return frappe.get_doc({
		'doctype': 'ToDo',
		'description': 'Fix a bug',
	}).insert()


# test for multiplier
