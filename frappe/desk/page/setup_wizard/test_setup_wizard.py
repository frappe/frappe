# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from unittest.mock import MagicMock, patch

import frappe
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
			patch.object(frappe, "get_active_apps", return_value=list(apps)),
			patch.object(frappe, "get_hooks", side_effect=fake_hooks(apps)),
		):
			url = setup_wizard.get_setup_wizard_url()
			builtin = setup_wizard.site_requires_builtin_wizard()
			return url, builtin

	def test_defaults_to_desk(self):
		url, builtin = self.resolve({"frappe": {}})
		self.assertEqual(url, "/desk/setup-wizard")
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
		self.assertEqual(url, "/desk/setup-wizard")
		self.assertTrue(builtin)

	def test_complete_hook_forces_desk(self):
		url, builtin = self.resolve(
			{
				"suite": {"setup_wizard_url": ["/suite/setup"]},
				"crm": {"setup_wizard_complete": ["crm.setup.after_complete"]},
			}
		)
		self.assertEqual(url, "/desk/setup-wizard")
		self.assertTrue(builtin)


class TestCompleteAppSetup(IntegrationTestCase):
	def test_setup_jobs_are_not_released_by_intermediate_commits(self):
		queue = MagicMock(count=0)
		enqueue_counts_during_setup = []

		def setup_task(_args):
			frappe.enqueue("frappe.utils.background_jobs.get_queue_list", enqueue_after_commit=True)
			frappe.db.commit()  # Exercise an intermediate setup commit; nosemgrep
			enqueue_counts_during_setup.append(queue.enqueue_call.call_count)

		stages = [{"tasks": [{"fn": setup_task, "args": frappe._dict()}]}]
		with (
			patch("frappe.utils.background_jobs.get_queue", return_value=queue),
			patch.object(setup_wizard, "get_setup_wizard_completed_apps", return_value=[]),
			patch.object(setup_wizard, "run_setup_success"),
			patch.object(setup_wizard, "apply_telemetry_preference"),
			patch.object(setup_wizard, "clear_cache_after_maintenance"),
			patch("frappe.utils.telemetry.capture"),
		):
			setup_wizard.process_setup_stages(stages, frappe._dict())

		self.assertEqual(enqueue_counts_during_setup, [0])
		queue.enqueue_call.assert_not_called()
		frappe.db.commit()  # Release callbacks at the request's final commit; nosemgrep
		queue.enqueue_call.assert_called_once()

	def test_setup_jobs_are_discarded_after_a_handled_failure(self):
		queue = MagicMock(count=0)

		def failing_setup_task(_args):
			frappe.enqueue("frappe.utils.background_jobs.get_queue_list", enqueue_after_commit=True)
			frappe.db.commit()  # Exercise an intermediate setup commit; nosemgrep
			raise RuntimeError

		stages = [{"tasks": [{"fn": failing_setup_task, "args": frappe._dict()}]}]
		with (
			patch("frappe.utils.background_jobs.get_queue", return_value=queue),
			patch.object(setup_wizard, "get_setup_wizard_completed_apps", return_value=[]),
			patch.object(setup_wizard, "handle_setup_exception"),
			patch.object(setup_wizard, "clear_cache_after_maintenance"),
			patch.object(frappe, "log_error"),
			patch("frappe.utils.telemetry.capture"),
		):
			setup_wizard.process_setup_stages(stages, frappe._dict(), is_background_task=True)

		frappe.db.commit()  # Prove a later commit cannot release cancelled jobs; nosemgrep
		queue.enqueue_call.assert_not_called()

	def test_global_settings_defer_timezone_job_until_commit(self):
		args = frappe._dict(language="French", lang="fr", timezone="Europe/Paris")
		with (
			patch.object(setup_wizard, "set_default_language"),
			patch.object(setup_wizard, "get_language_code", return_value="fr"),
			patch.object(frappe, "clear_cache"),
			patch.object(setup_wizard, "update_system_settings"),
			patch.object(setup_wizard, "create_or_update_user"),
			patch.object(frappe, "enqueue") as enqueue,
			patch.object(frappe.db, "commit") as commit,
		):
			setup_wizard.update_global_settings(args)

		commit.assert_not_called()
		enqueue.assert_called_once_with(
			setup_wizard.set_timezone,
			timezone="Europe/Paris",
			enqueue_after_commit=True,
		)

	def test_post_setup_does_not_commit_before_completion_marker(self):
		with (
			patch.object(setup_wizard, "disable_future_access"),
			patch.object(frappe, "clear_cache"),
			patch.object(frappe, "get_cached_doc", return_value=None),
			patch.object(frappe.db, "commit") as commit,
		):
			setup_wizard.run_post_setup_complete({})

		commit.assert_not_called()

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
