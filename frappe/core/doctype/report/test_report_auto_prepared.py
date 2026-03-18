from unittest.mock import patch

import frappe
from frappe.desk.query_report import run
from frappe.tests import UnitTestCase


class TestAutoPreparedReport(UnitTestCase):
	def make_script_report(self, report_name: str):
		"""Create an unsaved script report with isolated cache keys for tests."""
		report = frappe.get_doc(
			{
				"doctype": "Report",
				"name": report_name,
				"report_name": report_name,
				"ref_doctype": "User",
				"report_type": "Script Report",
				"is_standard": "No",
				"prepared_report": 0,
			}
		)
		self.addCleanup(frappe.cache().delete_value, report.get_execution_time_cache_key())
		self.addCleanup(frappe.cache().delete_value, report.get_auto_prepared_report_state_cache_key())
		return report

	def test_execute_script_report_auto_prepared_hysteresis(self):
		"""Enable auto prepared mode after repeated slow runs and clear it after fast runs."""
		report = self.make_script_report("Test Auto Prepared Script Report")

		with (
			patch.object(report, "execute_script", return_value=[[], []]),
			patch(
				"frappe.core.doctype.report.report.time.monotonic",
				side_effect=[0, 16, 20, 28, 30, 46, 50, 58, 60, 69, 70, 78],
			),
		):
			# A single slow run should not be enough to switch modes.
			report.execute_script_report({})
			self.assertFalse(report.is_auto_prepared_report_enabled())

			# Another run that is still below the repeated-slow threshold keeps it disabled.
			report.execute_script_report({})
			self.assertFalse(report.is_auto_prepared_report_enabled())

			# Two of the last three runs are now slow enough to enable background mode.
			report.execute_script_report({})
			self.assertTrue(report.is_auto_prepared_report_enabled())
			self.assertFalse(report.prepared_report)

			# Fast runs should not immediately clear the adaptive state.
			report.execute_script_report({})
			self.assertTrue(report.is_auto_prepared_report_enabled())

			report.execute_script_report({})
			self.assertTrue(report.is_auto_prepared_report_enabled())

			# Three consecutive fast runs should disable the adaptive prepared path again.
			report.execute_script_report({})
			self.assertFalse(report.is_auto_prepared_report_enabled())

	def test_query_report_uses_auto_prepared_path(self):
		"""Use the prepared-report branch when adaptive backgrounding says it should."""
		report = self.make_script_report("Test Query Report Auto Prepared Path")
		self.assertFalse(report.prepared_report)

		with (
			# Keep the test focused on routing rather than unrelated validation or permissions.
			patch("frappe.desk.query_report.validate_filters_permissions"),
			patch("frappe.desk.query_report.get_report_doc", return_value=report),
			patch("frappe.desk.query_report.frappe.has_permission", return_value=True),
			patch.object(report, "should_run_as_prepared_report", return_value=True),
			patch(
				"frappe.desk.query_report.get_prepared_report_result",
				return_value={"prepared_report": True, "doc": None},
			) as get_prepared_report_result,
			patch("frappe.desk.query_report.generate_report_result") as generate_report_result,
		):
			result = run(report.name)

		# Once the adaptive flag is on, query_report.run should serve the prepared path.
		self.assertTrue(result["prepared_report"])
		get_prepared_report_result.assert_called_once()
		generate_report_result.assert_not_called()
