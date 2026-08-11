# Copyright (c) 2024, Frappe Technologies and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.desk.doctype.system_health_report.system_health_report import get_scheduler_health_status
from frappe.desk.form.load import getdoc
from frappe.tests import IntegrationTestCase, UnitTestCase

HEALTH_REPORT_MODULE = "frappe.desk.doctype.system_health_report.system_health_report"


class TestSchedulerHealthStatus(UnitTestCase):
	@patch(f"{HEALTH_REPORT_MODULE}.get_scheduler_status", return_value={"status": "active"})
	@patch(f"{HEALTH_REPORT_MODULE}.is_schduler_process_running", return_value=True)
	@patch(f"{HEALTH_REPORT_MODULE}.is_dormant", return_value=True)
	def test_dormant(self, _is_dormant, _is_process_running, _get_scheduler_status):
		self.assertEqual(get_scheduler_health_status(), "Dormant")

	@patch(f"{HEALTH_REPORT_MODULE}.get_scheduler_status", return_value={"status": "active"})
	@patch(f"{HEALTH_REPORT_MODULE}.is_schduler_process_running", return_value=True)
	@patch(f"{HEALTH_REPORT_MODULE}.is_dormant", return_value=False)
	def test_active(self, _is_dormant, _is_process_running, _get_scheduler_status):
		self.assertEqual(get_scheduler_health_status(), "Active")

	@patch(f"{HEALTH_REPORT_MODULE}.get_scheduler_status", return_value={"status": "inactive"})
	@patch(f"{HEALTH_REPORT_MODULE}.is_schduler_process_running", return_value=True)
	@patch(f"{HEALTH_REPORT_MODULE}.is_dormant", return_value=False)
	def test_inactive(self, _is_dormant, _is_process_running, _get_scheduler_status):
		self.assertEqual(get_scheduler_health_status(), "Inactive")

	@patch(f"{HEALTH_REPORT_MODULE}.get_scheduler_status", return_value={"status": "active"})
	@patch(f"{HEALTH_REPORT_MODULE}.is_schduler_process_running", return_value=False)
	def test_process_not_found(self, _is_process_running, _get_scheduler_status):
		self.assertEqual(get_scheduler_health_status(), "Process Not Found")

	@patch(f"{HEALTH_REPORT_MODULE}.get_scheduler_status", return_value={"status": "active"})
	@patch(
		f"{HEALTH_REPORT_MODULE}.is_schduler_process_running",
		side_effect=Exception("redis_queue missing in common_site_config.json"),
	)
	def test_redis_unavailable(self, _is_process_running, _get_scheduler_status):
		self.assertEqual(get_scheduler_health_status(), "Redis Unavailable")


class TestSystemHealthReport(IntegrationTestCase):
	def test_it_works(self):
		getdoc("System Health Report", "System Health Report")
