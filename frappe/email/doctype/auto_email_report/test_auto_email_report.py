# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import json

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import add_to_date, get_link_to_form, today
from frappe.utils.data import is_html


class UnitTestAutoEmailReport(UnitTestCase):
	"""
	Unit tests for AutoEmailReport.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestAutoEmailReport(IntegrationTestCase):
	def test_auto_email(self) -> None:
		frappe.delete_doc("Auto Email Report", "Permitted Documents For User")

		auto_email_report = get_auto_email_report()

		data = auto_email_report.get_report_content()

		self.assertTrue(is_html(data))
		self.assertTrue(str(get_link_to_form("Module Def", "Core")) in data)

		auto_email_report.format = "CSV"

		data = auto_email_report.get_report_content()
		self.assertTrue('"Language","Core"' in data)

		auto_email_report.format = "XLSX"

		data = auto_email_report.get_report_content()

	def test_dynamic_date_filters(self) -> None:
		auto_email_report = get_auto_email_report()

		auto_email_report.dynamic_date_period = "Weekly"
		auto_email_report.from_date_field = "from_date"
		auto_email_report.to_date_field = "to_date"

		auto_email_report.prepare_dynamic_filters()

		self.assertEqual(auto_email_report.filters["from_date"], add_to_date(today(), weeks=-1))
		self.assertEqual(auto_email_report.filters["to_date"], today())


def get_auto_email_report():
	if not frappe.db.exists("Auto Email Report", "Permitted Documents For User"):
		auto_email_report = frappe.get_doc(
			doctype="Auto Email Report",
			report="Permitted Documents For User",
			report_type="Script Report",
			user="Administrator",
			enabled=1,
			email_to="test@example.com",
			format="HTML",
			frequency="Daily",
			filters=json.dumps(dict(user="Administrator", doctype="DocType")),
		).insert()
	else:
		auto_email_report = frappe.get_doc("Auto Email Report", "Permitted Documents For User")

	return auto_email_report
