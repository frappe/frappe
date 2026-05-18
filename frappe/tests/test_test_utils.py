import logging
from datetime import timedelta

import frappe
from frappe.tests import IntegrationTestCase
from frappe.tests.utils.generators import get_missing_records_doctypes, get_modules
from frappe.utils.data import now_datetime


class TestTestUtils(IntegrationTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def test_document_assertions(self):
		currency = frappe.new_doc("Currency")
		currency.currency_name = "STONKS"
		currency.smallest_currency_fraction_value = 0.420_001
		currency.save()

		self.assertDocumentEqual(currency.as_dict(), currency)

	def test_thread_locals(self):
		frappe.flags.temp_flag_to_be_discarded = True

	def test_temp_setting_changes(self):
		current_setting = frappe.get_system_settings("logout_on_password_reset")

		with IntegrationTestCase.change_settings(
			"System Settings", {"logout_on_password_reset": int(not current_setting)}
		):
			updated_settings = frappe.get_single_value("System Settings", "logout_on_password_reset")
			self.assertNotEqual(current_setting, updated_settings)

		restored_settings = frappe.get_single_value("System Settings", "logout_on_password_reset")
		self.assertEqual(current_setting, restored_settings)

	def test_time_freezing(self):
		now = now_datetime()

		tomorrow = now + timedelta(days=1)
		with self.freeze_time(tomorrow):
			self.assertEqual(now_datetime(), tomorrow)

	def test_get_modules_returns_none_for_missing_doctype(self):
		"""DocTypes from uninstalled apps should resolve to (None, None) instead of raising."""
		get_modules.cache_clear()
		try:
			module, test_module = get_modules("Definitely Not A Real DocType")
		finally:
			get_modules.cache_clear()
		self.assertIsNone(module)
		self.assertIsNone(test_module)

	def test_get_missing_records_doctypes_skips_missing_doctype(self):
		"""Missing link targets should be skipped with a warning, not crash the walk."""
		get_modules.cache_clear()
		try:
			with self.assertLogs("frappe.testing.generators", level=logging.WARNING) as log_ctx:
				result = get_missing_records_doctypes("Definitely Not A Real DocType")
		finally:
			get_modules.cache_clear()
		self.assertEqual(result, [])
		self.assertTrue(
			any("Definitely Not A Real DocType" in line for line in log_ctx.output),
			f"Expected warning mentioning the missing doctype, got: {log_ctx.output}",
		)


def tearDownModule():
	"""assertions for ensuring tests didn't leave state behind"""
	assert "temp_flag_to_be_discarded" not in frappe.flags
	assert not frappe.db.exists("Currency", "STONKS")
