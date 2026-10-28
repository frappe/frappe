# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import json
from io import BytesIO

from pypdf import PdfReader

import frappe
from frappe.email.doctype.auto_email_report.auto_email_report import send_now
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, get_link_to_form, today
from frappe.utils.data import is_html


class TestAutoEmailReport(IntegrationTestCase):
	def test_auto_email(self):
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

		auto_email_report.format = "PDF"

		data = auto_email_report.get_report_content()
		PdfReader(stream=BytesIO(data))

	def test_user_cannot_run_report_as_privileged_user(self):
		report_manager = create_user_with_role("report_manager_81414@example.com", "Report Manager")

		frappe.set_user(report_manager)
		self.addCleanup(frappe.set_user, "Administrator")

		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(
				doctype="Auto Email Report",
				report="Permitted Documents For User",
				report_type="Script Report",
				user="Administrator",
				enabled=0,
				email_to="attacker@example.com",
				format="CSV",
				frequency="Daily",
				filters=json.dumps(dict(user="Administrator", doctype="DocType")),
			).insert()

		own_report = frappe.get_doc(
			doctype="Auto Email Report",
			report="Permitted Documents For User",
			report_type="Script Report",
			user=report_manager,
			enabled=0,
			email_to="self@example.com",
			format="CSV",
			frequency="Daily",
			filters=json.dumps(dict(user=report_manager, doctype="DocType")),
		).insert()
		self.assertEqual(own_report.user, report_manager)

		frappe.set_user("Administrator")
		admin_report = frappe.get_doc(
			doctype="Auto Email Report",
			report="Permitted Documents For User",
			report_type="Script Report",
			user="Administrator",
			enabled=0,
			email_to="admin@example.com",
			format="CSV",
			frequency="Daily",
			filters=json.dumps(dict(user="Administrator", doctype="DocType")),
		).insert()

		frappe.set_user(report_manager)
		admin_report = frappe.get_doc("Auto Email Report", admin_report.name)
		admin_report.email_to = "attacker@example.com"
		with self.assertRaises(frappe.PermissionError):
			admin_report.save()

		with self.assertRaises(frappe.PermissionError):
			send_now(admin_report.name)

	def test_system_manager_can_run_report_as_other_user(self):
		system_manager = create_user_with_role("system_manager_81414@example.com", "System Manager")

		frappe.set_user(system_manager)
		self.addCleanup(frappe.set_user, "Administrator")

		report = frappe.get_doc(
			doctype="Auto Email Report",
			report="Permitted Documents For User",
			report_type="Script Report",
			user="Administrator",
			enabled=0,
			email_to="admin@example.com",
			format="CSV",
			frequency="Daily",
			filters=json.dumps(dict(user="Administrator", doctype="DocType")),
		).insert()
		self.assertEqual(report.user, "Administrator")

	def test_dynamic_date_filters(self):
		auto_email_report = get_auto_email_report()

		auto_email_report.dynamic_date_period = "Weekly"
		auto_email_report.from_date_field = "from_date"
		auto_email_report.to_date_field = "to_date"

		auto_email_report.prepare_dynamic_filters()

		self.assertEqual(auto_email_report.filters["from_date"], add_to_date(today(), weeks=-1))
		self.assertEqual(auto_email_report.filters["to_date"], today())


def create_user_with_role(email, role):
	if not frappe.db.exists("User", email):
		user = frappe.get_doc(doctype="User", email=email, first_name=role, send_welcome_email=0)
		user.append("roles", {"role": role})
		user.insert(ignore_permissions=True)
	return email


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
