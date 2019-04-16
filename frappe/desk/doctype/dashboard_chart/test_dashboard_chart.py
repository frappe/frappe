# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import unittest, frappe
from frappe.utils import getdate
from frappe.desk.doctype.dashboard_chart.dashboard_chart import (get,
	get_period_ending)

class TestDashboardChart(unittest.TestCase):
	def test_period_ending(self):
		self.assertEqual(get_period_ending('2019-04-10', 'Daily'),
			getdate('2019-04-10'))

		# fun fact: week ends on the day before 1st Jan of the year.
		# for 2019 it is Monday
		self.assertEqual(get_period_ending('2019-04-10', 'Weekly'),
			getdate('2019-04-15'))

		self.assertEqual(get_period_ending('2019-04-10', 'Monthly'),
			getdate('2019-04-30'))
		self.assertEqual(get_period_ending('2019-04-30', 'Monthly'),
			getdate('2019-04-30'))
		self.assertEqual(get_period_ending('2019-03-31', 'Monthly'),
			getdate('2019-03-31'))

		self.assertEqual(get_period_ending('2019-04-10', 'Quarterly'),
			getdate('2019-06-30'))
		self.assertEqual(get_period_ending('2019-06-30', 'Quarterly'),
			getdate('2019-06-30'))
		self.assertEqual(get_period_ending('2019-10-01', 'Quarterly'),
			getdate('2019-12-31'))

	def test_dashboard_chart(self):
		if frappe.db.exists('Dashboard Chart', 'Test Dashboard Chart'):
			frappe.delete_doc('Dashboard Chart', 'Test Dashboard Chart')

		frappe.get_doc(dict(
			doctype = 'Dashboard Chart',
			chart_name = 'Test Dashboard Chart',
			chart_type = 'Count',
			document_type = 'DocType',
			based_on = 'creation',
			timespan = 'Last Year',
			time_interval = 'Monthly',
			filters_json = '{}',
			timeseries = 1
		)).insert()

		result = get(chart_name ='Test Dashboard Chart',
			to_date = '2019-04-11', refresh = 1)
		self.assertEqual(result.get('labels')[0], '2018-04-30')
		self.assertEqual(result.get('labels')[1], '2018-05-31')
		self.assertEqual(result.get('labels')[2], '2018-06-30')
		self.assertEqual(result.get('labels')[3], '2018-07-31')
		self.assertEqual(result.get('labels')[4], '2018-08-31')
		self.assertEqual(result.get('labels')[5], '2018-09-30')
		self.assertEqual(result.get('labels')[6], '2018-10-31')
		self.assertEqual(result.get('labels')[7], '2018-11-30')
		self.assertEqual(result.get('labels')[8], '2018-12-31')
		self.assertEqual(result.get('labels')[9], '2019-01-31')
		self.assertEqual(result.get('labels')[10], '2019-02-28')
		self.assertEqual(result.get('labels')[11], '2019-03-31')
		self.assertEqual(result.get('labels')[12], '2019-04-30')

		# self.assertEqual(result.get('datasets')[0].get('values')[:-1],
		# 	[44, 28, 8, 11, 2, 6, 18, 6, 4, 5, 15, 13])

		frappe.db.rollback()

	def test_empty_dashboard_chart(self):
		if frappe.db.exists('Dashboard Chart', 'Test Empty Dashboard Chart'):
			frappe.delete_doc('Dashboard Chart', 'Test Empty Dashboard Chart')

		frappe.db.sql('delete from `tabError Log`')

		frappe.get_doc(dict(
			doctype = 'Dashboard Chart',
			chart_name = 'Test Empty Dashboard Chart',
			chart_type = 'Count',
			document_type = 'Error Log',
			based_on = 'creation',
			timespan = 'Last Year',
			time_interval = 'Monthly',
			filters_json = '{}',
			timeseries = 1
		)).insert()

		result = get(chart_name ='Test Empty Dashboard Chart',
			to_date = '2019-04-11', refresh = 1)
		self.assertEqual(result.get('labels')[0], '2018-04-30')
		self.assertEqual(result.get('labels')[1], '2018-05-31')
		self.assertEqual(result.get('labels')[2], '2018-06-30')
		self.assertEqual(result.get('labels')[3], '2018-07-31')
		self.assertEqual(result.get('labels')[4], '2018-08-31')
		self.assertEqual(result.get('labels')[5], '2018-09-30')
		self.assertEqual(result.get('labels')[6], '2018-10-31')
		self.assertEqual(result.get('labels')[7], '2018-11-30')
		self.assertEqual(result.get('labels')[8], '2018-12-31')
		self.assertEqual(result.get('labels')[9], '2019-01-31')
		self.assertEqual(result.get('labels')[10], '2019-02-28')
		self.assertEqual(result.get('labels')[11], '2019-03-31')
		self.assertEqual(result.get('labels')[12], '2019-04-30')

		frappe.db.rollback()

	def test_chart_wih_one_value(self):
		if frappe.db.exists('Dashboard Chart', 'Test Empty Dashboard Chart 2'):
			frappe.delete_doc('Dashboard Chart', 'Test Empty Dashboard Chart 2')

		frappe.db.sql('delete from `tabError Log`')

		# create one data point
		frappe.get_doc(dict(doctype = 'Error Log', creation = '2018-06-01 00:00:00')).insert()

		frappe.get_doc(dict(
			doctype = 'Dashboard Chart',
			chart_name = 'Test Empty Dashboard Chart 2',
			chart_type = 'Count',
			document_type = 'Error Log',
			based_on = 'creation',
			timespan = 'Last Year',
			time_interval = 'Monthly',
			filters_json = '{}',
			timeseries = 1
		)).insert()

		result = get(chart_name ='Test Empty Dashboard Chart 2',
			to_date = '2019-04-11', refresh = 1)
		self.assertEqual(result.get('labels')[0], '2018-04-30')
		self.assertEqual(result.get('labels')[1], '2018-05-31')
		self.assertEqual(result.get('labels')[2], '2018-06-30')
		self.assertEqual(result.get('labels')[3], '2018-07-31')
		self.assertEqual(result.get('labels')[4], '2018-08-31')
		self.assertEqual(result.get('labels')[5], '2018-09-30')
		self.assertEqual(result.get('labels')[6], '2018-10-31')
		self.assertEqual(result.get('labels')[7], '2018-11-30')
		self.assertEqual(result.get('labels')[8], '2018-12-31')
		self.assertEqual(result.get('labels')[9], '2019-01-31')
		self.assertEqual(result.get('labels')[10], '2019-02-28')
		self.assertEqual(result.get('labels')[11], '2019-03-31')
		self.assertEqual(result.get('labels')[12], '2019-04-30')

		# only 1 data point with value
		self.assertEqual(result.get('datasets')[0].get('values')[2], 1)

		frappe.db.rollback()


