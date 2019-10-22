# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest, json
from frappe.utils import get_link_to_form, today, add_to_date
from frappe.utils.report_rendering import (get_report_content, prepare_dynamic_filters)
from frappe.utils.data import is_html

# test_records = frappe.get_test_records('Auto Email Report')

class TestAutoEmailReport(unittest.TestCase):
	def test_auto_email(self):
		frappe.delete_doc('Auto Email Report', 'Permitted Documents For User')

		auto_email_report = get_auto_email_report()

		data = get_report_content(
			auto_email_report.report,
			auto_email_report.filters,
			auto_email_report.format,
			auto_email_report.no_of_rows,
			auto_email_report.description,
			auto_email_report.user,
			auto_email_report.data_modified_till,
			auto_email_report.from_date_field,
			auto_email_report.to_date_field,
			auto_email_report.dynamic_date_period,
			additional_params = {
				'edit_report_settings': get_link_to_form('Auto Email Report', auto_email_report.name)
				}
		)
		self.assertTrue(is_html(data))
		print("data", data)
		self.assertTrue('<td>' + str(get_link_to_form('Module Def', 'Core'))+'</td>' in data)
		
		auto_email_report.format = 'CSV'

		data = get_report_content(
			auto_email_report.report,
			auto_email_report.filters,
			auto_email_report.format,
			auto_email_report.no_of_rows,
			auto_email_report.description,
			auto_email_report.user,
			auto_email_report.data_modified_till,
			auto_email_report.from_date_field,
			auto_email_report.to_date_field,
			auto_email_report.dynamic_date_period,
			additional_params = {
				'edit_report_settings': get_link_to_form('Auto Email Report', auto_email_report.name)
				}
		)
		self.assertTrue('"Language","Core"' in data)

		auto_email_report.format = 'XLSX'

		data = get_report_content(
			auto_email_report.report,
			auto_email_report.filters,
			auto_email_report.format,
			auto_email_report.no_of_rows,
			auto_email_report.description,
			auto_email_report.user,
			auto_email_report.data_modified_till,
			auto_email_report.from_date_field,
			auto_email_report.to_date_field,
			auto_email_report.dynamic_date_period,
			additional_params = {
				'edit_report_settings': get_link_to_form('Auto Email Report', auto_email_report.name)
				}
		)


	def test_dynamic_date_filters(self):
		auto_email_report = get_auto_email_report()

		auto_email_report.dynamic_date_period = 'Weekly'
		auto_email_report.from_date_field = 'from_date'
		auto_email_report.to_date_field = 'to_date'

		auto_email_report.filters = prepare_dynamic_filters(auto_email_report.filters, auto_email_report.dynamic_date_period, auto_email_report.from_date_field, auto_email_report.to_date_field)
		self.assertEqual(auto_email_report.filters['from_date'], add_to_date(today(), weeks=-1))
		self.assertEqual(auto_email_report.filters['to_date'], today())


def get_auto_email_report():
	if not frappe.db.exists('Auto Email Report', 'Permitted Documents For User'):
		auto_email_report = frappe.get_doc(dict(
			doctype='Auto Email Report',
			report='Permitted Documents For User',
			report_type='Script Report',
			user='Administrator',
			enabled=1,
			email_to='test@example.com',
			format='HTML',
			frequency='Daily',
			filters=json.dumps(dict(user='Administrator', doctype='DocType'))
		)).insert()
	else:
		auto_email_report = frappe.get_doc('Auto Email Report', 'Permitted Documents For User')

	return auto_email_report