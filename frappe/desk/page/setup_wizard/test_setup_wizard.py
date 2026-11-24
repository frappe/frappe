# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from unittest.mock import MagicMock, patch

import frappe
import frappe.client
from frappe.desk.page.setup_wizard import setup_wizard
from frappe.tests import IntegrationTestCase, UnitTestCase, set_user
from frappe.utils.synchronization import LockTimeoutError


def fake_hooks(apps):
	def get_hooks(hook=None, default=None, app_name=None):
		if app_name:
			return apps.get(app_name, {})
		merged = []
		for app_hooks in apps.values():
			merged += app_hooks.get(hook, [])
		return merged

	return get_hooks


class TestSetupWizardUrl(UnitTestCase):
	def resolve(self, apps):
		with (
			patch.object(frappe, "get_installed_apps", return_value=list(apps)),
			patch.object(frappe, "get_hooks", side_effect=fake_hooks(apps)),
		):
			url = setup_wizard.get_setup_wizard_url()
			builtin = setup_wizard.site_requires_builtin_wizard()
			return url, builtin

	def test_defaults_to_desk(self):
		url, builtin = self.resolve({"frappe": {}})
		self.assertEqual(url, "/app/setup-wizard")
		self.assertFalse(builtin)

	def test_uses_app_url(self):
		url, builtin = self.resolve({"suite": {"setup_wizard_url": ["/suite/setup"]}})
		self.assertEqual(url, "/suite/setup")
		self.assertFalse(builtin)

	def test_last_app_wins(self):
		url, _ = self.resolve(
			{
				"suite": {"setup_wizard_url": ["/suite/setup"]},
				"gameplan": {"setup_wizard_url": ["/gameplan/setup"]},
			}
		)
		self.assertEqual(url, "/gameplan/setup")

	def test_stage_app_forces_desk(self):
		url, builtin = self.resolve(
			{
				"suite": {"setup_wizard_url": ["/suite/setup"]},
				"erpnext": {"setup_wizard_stages": ["erpnext.setup.get_setup_stages"]},
			}
		)
		self.assertEqual(url, "/app/setup-wizard")
		self.assertTrue(builtin)

	def test_complete_hook_forces_desk(self):
		url, builtin = self.resolve(
			{
				"suite": {"setup_wizard_url": ["/suite/setup"]},
				"crm": {"setup_wizard_complete": ["crm.setup.after_complete"]},
			}
		)
		self.assertEqual(url, "/app/setup-wizard")
		self.assertTrue(builtin)


class TestCompleteAppSetup(IntegrationTestCase):
	def test_a_site_without_a_region_still_gets_the_site_defaults(self):
		# Like a Frappe Cloud v2 site: no region, so no time zone or formats saved either.
		fields = [
			"backup_limit",
			"language",
			"time_zone",
			"date_format",
			"number_format",
			"rounding_method",
			"enable_telemetry",
		]
		before = frappe.db.get_singles_dict("System Settings")

		def restore():
			# A field that had no row falls back to its default; a NULL row would not.
			for field in fields:
				if field in before:
					frappe.db.set_single_value("System Settings", field, before[field])
				else:
					frappe.db.delete("Singles", {"doctype": "System Settings", "field": field})

		self.addCleanup(restore)
		frappe.db.set_single_value(
			"System Settings",
			{
				"backup_limit": 1,
				"language": None,
				"time_zone": None,
				"date_format": None,
				"number_format": None,
			},
		)
		# The time zone it falls back to is read through the System Settings caches.
		frappe.local.system_settings = None
		frappe.client_cache.delete_value(frappe.get_document_cache_key("System Settings", "System Settings"))

		setup_wizard.update_system_settings({})

		self.assertEqual(frappe.db.get_single_value("System Settings", "backup_limit"), 3)
		self.assertEqual(
			frappe.db.get_single_value("System Settings", "rounding_method"), "Banker's Rounding"
		)
		self.assertEqual(frappe.db.get_single_value("System Settings", "language"), "en")
		self.assertEqual(frappe.db.get_single_value("System Settings", "time_zone"), "Asia/Kolkata")
		self.assertEqual(frappe.db.get_single_value("System Settings", "date_format"), "yyyy-mm-dd")
		self.assertEqual(frappe.db.get_single_value("System Settings", "number_format"), "#,###.##")
		# An app's setup saves a single setting, like the telemetry choice, through the doc.
		frappe.client.set_value("System Settings", "System Settings", "enable_telemetry", 0)

	def test_a_failed_prefilled_setup_is_not_tried_again(self):
		with (
			patch.object(setup_wizard, "get_prefilled_setup_args", return_value={"country": "India"}),
			patch.object(setup_wizard, "complete_app_setup", side_effect=RuntimeError("boom")),
			patch.object(frappe.db, "commit"),
			patch.object(frappe, "log_error"),
		):
			setup_wizard.complete_prefilled_setup()
		self.addCleanup(frappe.defaults.clear_default, setup_wizard.PREFILLED_SETUP_FAILED)

		self.assertTrue(frappe.db.get_default(setup_wizard.PREFILLED_SETUP_FAILED))
		self.assertIsNone(setup_wizard.get_prefilled_setup_args())
		# Kept even when the login was a GET, like an email link.
		self.assertTrue(frappe.local.flags.commit)

	def test_needs_system_manager(self):
		with set_user("Guest"):
			self.assertRaises(frappe.PermissionError, setup_wizard.complete_app_setup)

	def test_refuses_builtin_site(self):
		with patch.object(setup_wizard, "site_requires_builtin_wizard", return_value=True):
			self.assertRaises(frappe.ValidationError, setup_wizard.complete_app_setup)

	def test_skips_when_already_complete(self):
		with (
			patch.object(setup_wizard, "site_requires_builtin_wizard", return_value=False),
			patch.object(frappe, "is_setup_complete", return_value=True),
			patch.object(setup_wizard, "process_setup_stages") as process_stages,
		):
			self.assertEqual(setup_wizard.complete_app_setup(), {"status": "ok"})
			process_stages.assert_not_called()

	def test_lock_timeout_never_reports_false_success(self):
		lock = MagicMock()
		lock.__enter__.side_effect = LockTimeoutError
		with (
			patch.object(setup_wizard, "site_requires_builtin_wizard", return_value=False),
			patch.object(setup_wizard, "filelock", return_value=lock),
		):
			with patch.object(frappe, "is_setup_complete", return_value=False):
				self.assertRaises(frappe.ValidationError, setup_wizard.complete_app_setup)
			with patch.object(frappe, "is_setup_complete", return_value=True):
				self.assertEqual(setup_wizard.complete_app_setup(), {"status": "ok"})


# An app that wants setup finished at login.
OPTED_IN = {"setup_wizard_auto_complete": [True]}


class TestPrefilledSetup(IntegrationTestCase):
	def setUp(self):
		patcher = patch.object(frappe, "is_setup_complete", return_value=False)
		patcher.start()
		self.addCleanup(patcher.stop)

	def args(self, apps=None):
		apps = apps or {"frappe": {}, "suite": OPTED_IN}
		with (
			patch.object(frappe, "get_installed_apps", return_value=list(apps)),
			patch.object(frappe, "get_hooks", side_effect=fake_hooks(apps)),
		):
			return setup_wizard.get_prefilled_setup_args()

	@IntegrationTestCase.change_settings(
		"System Settings", country="India", time_zone="Asia/Kolkata", currency="INR"
	)
	def test_uses_the_region_frappe_cloud_saved(self):
		args = self.args()
		self.assertEqual(
			(args["country"], args["timezone"], args["currency"]), ("India", "Asia/Kolkata", "INR")
		)

	@IntegrationTestCase.change_settings(
		"System Settings", country="India", time_zone="Asia/Kolkata", currency="INR"
	)
	def test_keeps_the_wizard_unless_an_app_opts_in(self):
		self.assertIsNone(self.args({"frappe": {}, "raven": {"setup_wizard_success": ["raven.setup"]}}))

	@IntegrationTestCase.change_settings(
		"System Settings", country="India", time_zone="Asia/Kolkata", currency="INR"
	)
	def test_a_hook_set_to_false_does_not_opt_in(self):
		self.assertIsNone(self.args({"frappe": {}, "suite": {"setup_wizard_auto_complete": [False]}}))

	@IntegrationTestCase.change_settings("System Settings", country=None)
	def test_a_site_without_a_saved_region_keeps_the_wizard(self):
		self.assertIsNone(self.args())

	@IntegrationTestCase.change_settings("System Settings", country=None)
	def test_frappe_cloud_v2_saves_no_region(self):
		with patch.dict(
			frappe.conf, {"pilot_endpoint": "https://pilot.example.com", "pilot_auth_token": "t"}
		):
			self.assertIsNotNone(self.args())

	@IntegrationTestCase.change_settings(
		"System Settings", country="India", time_zone="Asia/Kolkata", currency="INR"
	)
	def test_an_app_with_wizard_stages_keeps_the_wizard(self):
		self.assertIsNone(
			self.args(
				{
					"suite": OPTED_IN,
					"erpnext": {
						"setup_wizard_stages": ["erpnext.setup.setup_wizard.setup_wizard.get_setup_stages"]
					},
				}
			)
		)

	@IntegrationTestCase.change_settings(
		"System Settings", country="India", time_zone="Asia/Kolkata", currency="INR"
	)
	def test_an_app_with_its_own_setup_page_keeps_it(self):
		self.assertIsNone(self.args({"suite": {**OPTED_IN, "setup_wizard_url": ["/suite/setup"]}}))

	@IntegrationTestCase.change_settings(
		"System Settings", country="India", time_zone="Asia/Kolkata", currency="INR"
	)
	def test_only_a_system_manager_login_finishes_setup(self):
		with set_user("Guest"):
			self.assertIsNone(self.args())
