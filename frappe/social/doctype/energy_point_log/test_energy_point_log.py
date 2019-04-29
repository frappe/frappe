# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
from .energy_point_log import get_energy_points as _get_energy_points, create_review_points_log, review
from frappe.utils.testutils import add_custom_field, clear_custom_fields

class TestEnergyPointLog(unittest.TestCase):
	def tearDown(self):
		frappe.set_user('Administrator')
		frappe.db.sql('DELETE FROM `tabEnergy Point Log`')
		frappe.db.sql('DELETE FROM `tabEnergy Point Rule`')

	def test_user_energy_point(self):
		frappe.set_user('test@example.com')
		todo_point_rule = create_energy_point_rule_for_todo()
		energy_point_of_user = get_points('test@example.com')

		created_todo = create_a_todo()

		created_todo.status = 'Closed'
		created_todo.save()

		points_after_closing_todo = get_points('test@example.com')

		self.assertEquals(points_after_closing_todo, energy_point_of_user + todo_point_rule.points)

		created_todo.save()
		points_after_double_save = get_points('test@example.com')

		# point should not be awarded more than once for same doc
		self.assertEquals(points_after_double_save, energy_point_of_user + todo_point_rule.points)

	def test_points_based_on_multiplier_field(self):
		frappe.set_user('test@example.com')
		add_custom_field('ToDo', 'multiplier', 'Float')
		multiplier_value = 0.51

		todo_point_rule = create_energy_point_rule_for_todo('multiplier')
		energy_point_of_user = get_points('test@example.com')

		created_todo = create_a_todo()
		points_after_closing_todo = get_points('test@example.com')
		created_todo.status = 'Closed'
		created_todo.multiplier = multiplier_value
		created_todo.save()

		points_after_closing_todo = get_points('test@example.com')

		self.assertEquals(points_after_closing_todo, energy_point_of_user + round(todo_point_rule.points * multiplier_value))
		clear_custom_fields('ToDo')

	def test_disabled_energy_points(self):
		settings = frappe.get_single('Energy Point Settings')
		settings.enabled = 0
		settings.save()

		frappe.set_user('test@example.com')
		create_energy_point_rule_for_todo()
		energy_point_of_user = get_points('test@example.com')

		created_todo = create_a_todo()

		created_todo.status = 'Closed'
		created_todo.save()

		points_after_closing_todo = get_points('test@example.com')

		# no change in points
		self.assertEquals(points_after_closing_todo, energy_point_of_user)

		settings.enabled = 1
		settings.save()

	def test_review(self):
		created_todo = create_a_todo()
		review_points = 20
		create_review_points_log('test2@example.com', review_points)

		# reviewer
		frappe.set_user('test2@example.com')

		review_points_before_review = get_points('test2@example.com', 'review_points')
		self.assertEquals(review_points_before_review, review_points)

		# for appreciation
		appreciation_points = 5
		energy_points_before_review = get_points('test@example.com')
		review(created_todo, appreciation_points, 'test@example.com', 'good job')
		energy_points_after_review = get_points('test@example.com')
		review_points_after_review = get_points('test2@example.com', 'review_points')
		self.assertEquals(energy_points_after_review, energy_points_before_review + appreciation_points)
		self.assertEquals(review_points_after_review, review_points_before_review - appreciation_points)

		# for criticism
		criticism_points = 2
		energy_points_before_review = energy_points_after_review
		review_points_before_review = review_points_after_review
		review(created_todo, criticism_points, 'test@example.com', 'You could have done better.', 'Criticism')
		energy_points_after_review = get_points('test@example.com')
		review_points_after_review = get_points('test2@example.com', 'review_points')
		self.assertEquals(energy_points_after_review, energy_points_before_review - criticism_points)
		self.assertEquals(review_points_after_review, review_points_before_review - criticism_points)

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


def get_points(user, point_type='energy_points'):
	return _get_energy_points(user).get(point_type) or 0