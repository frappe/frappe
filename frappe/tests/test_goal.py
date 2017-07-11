# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import unittest
import frappe

from frappe.utils.goal import get_monthly_results, get_monthly_goal_graph_data
from frappe.test_runner import make_test_objects
import frappe.utils

class TestGoal(unittest.TestCase):
	def setUp(self):
		make_test_objects('Event', reset=True)

	def tearDown(self):
		frappe.db.sql('delete from `tabEvent`')
		# make_test_objects('Event', reset=True)
		frappe.db.commit()

	def test_get_monthly_results(self):
		'''Test monthly aggregation values of a field'''
		result_dict = get_monthly_results('Event', 'subject', 'event_type="Private"', 'count')

		from frappe.utils import today, formatdate
		self.assertEquals(result_dict[formatdate(today(), "MM-yyyy")], 2)

	def test_get_monthly_goal_graph_data(self):
		'''Test for accurate values in graph data (based on test_get_monthly_results)'''
		data = get_monthly_goal_graph_data('Test', 'Event', '_Test Event 1', 'color', 'description',
			'Event', 'subject', 'starts_on = "2014-01-01"', 'count')
		self.assertEquals(data['y_values'][-1], 2)