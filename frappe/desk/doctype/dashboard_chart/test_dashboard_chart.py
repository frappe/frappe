# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors

# See license.txt
from __future__ import unicode_literals

import unittest
from datetime import datetime
from unittest.mock import patch

from dateutil.relativedelta import relativedelta

import frappe
from frappe.desk.doctype.dashboard_chart.dashboard_chart import get
from frappe.tests.utils import FrappeTestCase
from frappe.utils import formatdate, get_last_day, getdate
from frappe.utils.dateutils import get_period, get_period_ending


class TestDashboardChart(FrappeTestCase):
	def test_period_ending(self):
		self.assertEqual(get_period_ending("2019-04-10", "Daily"), getdate("2019-04-10"))

		# week starts on monday
		with patch.object(frappe.utils.data, "get_first_day_of_the_week", return_value="Monday"):
			self.assertEqual(get_period_ending("2019-04-10", "Weekly"), getdate("2019-04-14"))

		self.assertEqual(get_period_ending("2019-04-10", "Monthly"), getdate("2019-04-30"))
		self.assertEqual(get_period_ending("2019-04-30", "Monthly"), getdate("2019-04-30"))
		self.assertEqual(get_period_ending("2019-03-31", "Monthly"), getdate("2019-03-31"))

		self.assertEqual(get_period_ending("2019-04-10", "Quarterly"), getdate("2019-06-30"))
		self.assertEqual(get_period_ending("2019-06-30", "Quarterly"), getdate("2019-06-30"))
		self.assertEqual(get_period_ending("2019-10-01", "Quarterly"), getdate("2019-12-31"))

	def test_dashboard_chart(self):
		if frappe.db.exists("Dashboard Chart", "Test Dashboard Chart"):
			frappe.delete_doc("Dashboard Chart", "Test Dashboard Chart")

		frappe.get_doc(
			dict(
				doctype="Dashboard Chart",
				chart_name="Test Dashboard Chart",
				chart_type="Count",
				document_type="DocType",
				based_on="creation",
				timespan="Last Year",
				time_interval="Monthly",
				filters_json="{}",
				timeseries=1,
			)
		).insert()

		cur_date = datetime.now() - relativedelta(years=1)

		result = get(chart_name="Test Dashboard Chart", refresh=1)

		for idx in range(13):
			month = get_last_day(cur_date)
			month = formatdate(month.strftime("%Y-%m-%d"))
			self.assertEqual(result.get("labels")[idx], get_period(month))
			cur_date += relativedelta(months=1)

	def test_empty_dashboard_chart(self):
		if frappe.db.exists("Dashboard Chart", "Test Empty Dashboard Chart"):
			frappe.delete_doc("Dashboard Chart", "Test Empty Dashboard Chart")

		frappe.db.sql("delete from `tabError Log`")

		frappe.get_doc(
			dict(
				doctype="Dashboard Chart",
				chart_name="Test Empty Dashboard Chart",
				chart_type="Count",
				document_type="Error Log",
				based_on="creation",
				timespan="Last Year",
				time_interval="Monthly",
				filters_json="[]",
				timeseries=1,
			)
		).insert()

		cur_date = datetime.now() - relativedelta(years=1)

		result = get(chart_name="Test Empty Dashboard Chart", refresh=1)

		for idx in range(13):
			month = get_last_day(cur_date)
			month = formatdate(month.strftime("%Y-%m-%d"))
			self.assertEqual(result.get("labels")[idx], get_period(month))
			cur_date += relativedelta(months=1)

	def test_chart_wih_one_value(self):
		if frappe.db.exists("Dashboard Chart", "Test Empty Dashboard Chart 2"):
			frappe.delete_doc("Dashboard Chart", "Test Empty Dashboard Chart 2")

		frappe.db.sql("delete from `tabError Log`")

		# create one data point
		frappe.get_doc(dict(doctype="Error Log", creation="2018-06-01 00:00:00")).insert()

		frappe.get_doc(
			dict(
				doctype="Dashboard Chart",
				chart_name="Test Empty Dashboard Chart 2",
				chart_type="Count",
				document_type="Error Log",
				based_on="creation",
				timespan="Last Year",
				time_interval="Monthly",
				filters_json="[]",
				timeseries=1,
			)
		).insert()

		cur_date = datetime.now() - relativedelta(years=1)

		result = get(chart_name="Test Empty Dashboard Chart 2", refresh=1)

		for idx in range(13):
			month = get_last_day(cur_date)
			month = formatdate(month.strftime("%Y-%m-%d"))
			self.assertEqual(result.get("labels")[idx], get_period(month))
			cur_date += relativedelta(months=1)

		# only 1 data point with value
		self.assertEqual(result.get("datasets")[0].get("values")[2], 0)

	def test_group_by_chart_type(self):
		if frappe.db.exists("Dashboard Chart", "Test Group By Dashboard Chart"):
			frappe.delete_doc("Dashboard Chart", "Test Group By Dashboard Chart")

		frappe.get_doc({"doctype": "ToDo", "description": "test"}).insert()

		frappe.get_doc(
			dict(
				doctype="Dashboard Chart",
				chart_name="Test Group By Dashboard Chart",
				chart_type="Group By",
				document_type="ToDo",
				group_by_based_on="status",
				filters_json="[]",
			)
		).insert()

		result = get(chart_name="Test Group By Dashboard Chart", refresh=1)
		todo_status_count = frappe.db.count("ToDo", {"status": result.get("labels")[0]})

		self.assertEqual(result.get("datasets")[0].get("values")[0], todo_status_count)

	def test_daily_dashboard_chart(self):
		insert_test_records()

		if frappe.db.exists("Dashboard Chart", "Test Daily Dashboard Chart"):
			frappe.delete_doc("Dashboard Chart", "Test Daily Dashboard Chart")

		frappe.get_doc(
			dict(
				doctype="Dashboard Chart",
				chart_name="Test Daily Dashboard Chart",
				chart_type="Sum",
				document_type="Communication",
				based_on="communication_date",
				value_based_on="rating",
				timespan="Select Date Range",
				time_interval="Daily",
				from_date=datetime(2019, 1, 6),
				to_date=datetime(2019, 1, 11),
				filters_json="[]",
				timeseries=1,
			)
		).insert()

		result = get(chart_name="Test Daily Dashboard Chart", refresh=1)

		self.assertEqual(result.get("datasets")[0].get("values"), [200.0, 400.0, 300.0, 0.0, 100.0, 0.0])
		self.assertEqual(
			result.get("labels"),
			["01-06-2019", "01-07-2019", "01-08-2019", "01-09-2019", "01-10-2019", "01-11-2019"],
		)

	def test_weekly_dashboard_chart(self):
		insert_test_records()

		if frappe.db.exists("Dashboard Chart", "Test Weekly Dashboard Chart"):
			frappe.delete_doc("Dashboard Chart", "Test Weekly Dashboard Chart")

		frappe.get_doc(
			dict(
				doctype="Dashboard Chart",
				chart_name="Test Weekly Dashboard Chart",
				chart_type="Sum",
				document_type="Communication",
				based_on="communication_date",
				value_based_on="rating",
				timespan="Select Date Range",
				time_interval="Weekly",
				from_date=datetime(2018, 12, 30),
				to_date=datetime(2019, 1, 15),
				filters_json="[]",
				timeseries=1,
			)
		).insert()

		with patch.object(frappe.utils.data, "get_first_day_of_the_week", return_value="Monday"):
			result = get(chart_name="Test Weekly Dashboard Chart", refresh=1)

			self.assertEqual(result.get("datasets")[0].get("values"), [50.0, 300.0, 800.0, 0.0])
			self.assertEqual(result.get("labels"), ["12-30-2018", "01-06-2019", "01-13-2019", "01-20-2019"])

	def test_avg_dashboard_chart(self):
		insert_test_records()

		if frappe.db.exists("Dashboard Chart", "Test Average Dashboard Chart"):
			frappe.delete_doc("Dashboard Chart", "Test Average Dashboard Chart")

		frappe.get_doc(
			dict(
				doctype="Dashboard Chart",
				chart_name="Test Average Dashboard Chart",
				chart_type="Average",
				document_type="Communication",
				based_on="communication_date",
				value_based_on="rating",
				timespan="Select Date Range",
				time_interval="Weekly",
				from_date=datetime(2018, 12, 30),
				to_date=datetime(2019, 1, 15),
				filters_json="[]",
				timeseries=1,
			)
		).insert()

		with patch.object(frappe.utils.data, "get_first_day_of_the_week", return_value="Monday"):
			result = get(chart_name="Test Average Dashboard Chart", refresh=1)
			self.assertEqual(result.get("labels"), ["12-30-2018", "01-06-2019", "01-13-2019", "01-20-2019"])
			self.assertEqual(result.get("datasets")[0].get("values"), [50.0, 150.0, 266.6666666666667, 0.0])

	def test_user_date_label_dashboard_chart(self):
		frappe.delete_doc_if_exists("Dashboard Chart", "Test Dashboard Chart Date Label")

		frappe.get_doc(
			dict(
				doctype="Dashboard Chart",
				chart_name="Test Dashboard Chart Date Label",
				chart_type="Count",
				document_type="DocType",
				based_on="creation",
				timespan="Select Date Range",
				time_interval="Weekly",
				from_date=datetime(2018, 12, 30),
				to_date=datetime(2019, 1, 15),
				filters_json="[]",
				timeseries=1,
			)
		).insert()

		with patch.object(frappe.utils.data, "get_user_date_format", return_value="dd.mm.yyyy"):
			result = get(chart_name="Test Dashboard Chart Date Label")
			self.assertEqual(
				sorted(result.get("labels")), sorted(["05.01.2019", "12.01.2019", "19.01.2019"])
			)

		with patch.object(frappe.utils.data, "get_user_date_format", return_value="mm-dd-yyyy"):
			result = get(chart_name="Test Dashboard Chart Date Label")
			self.assertEqual(
				sorted(result.get("labels")), sorted(["01-19-2019", "01-05-2019", "01-12-2019"])
			)


def insert_test_records():
	create_new_communication("Communication 1", datetime(2018, 12, 30), 50)
	create_new_communication("Communication 2", datetime(2019, 1, 4), 100)
	create_new_communication("Communication 3", datetime(2019, 1, 6), 200)
	create_new_communication("Communication 4", datetime(2019, 1, 7), 400)
	create_new_communication("Communication 5", datetime(2019, 1, 8), 300)
	create_new_communication("Communication 6", datetime(2019, 1, 10), 100)


def create_new_communication(subject, date, rating):
	communication = {
		"doctype": "Communication",
		"subject": subject,
		"rating": rating,
		"communication_date": date,
	}
	comm = frappe.get_doc(communication)
	if not frappe.db.exists("Communication", {"subject": comm.subject}):
		comm.insert()
