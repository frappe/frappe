import types
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import frappe
from frappe.commands.testing import main as run_tests
from frappe.tests import UnitTestCase
from frappe.tests.utils.sqlite_test_shard import preload_modules, prepare_site, run_module, run_modules


class TestSQLiteTestShard(UnitTestCase):
	@patch("frappe.tests.utils.generators._clear_test_log")
	def test_runner_can_preserve_prepared_test_records(self, clear_test_log):
		with (
			patch("frappe.testing.TestRunner") as test_runner,
			patch("frappe.testing.discover_module_tests"),
			patch("frappe.testing.environment._initialize_test_environment"),
			patch("frappe.testing.environment._cleanup_after_tests"),
		):
			test_runner.return_value.iterRun.return_value = []
			run_tests(
				site="test_site",
				app="frappe",
				module="frappe.tests.test_db",
				preserve_test_records=True,
			)

		clear_test_log.assert_not_called()

	@patch("frappe.tests.utils.sqlite_test_shard._clear_test_log")
	def test_prepare_site_creates_reusable_test_state(self, clear_test_log):
		with patch.object(frappe, "destroy") as destroy:
			with (
				patch("frappe.testing.environment._initialize_test_environment") as initialize,
				patch("frappe.testing.environment.IntegrationTestPreparation") as preparation,
				patch("frappe.testing.environment._cleanup_after_tests") as cleanup,
			):
				prepare_site("test_site", "frappe")

		initialize.assert_called_once()
		clear_test_log.assert_called_once_with()
		preparation.return_value.assert_called_once()
		cleanup.assert_called_once_with()
		destroy.assert_called_once_with()

	def test_preload_closes_fork_unsafe_cache_thread(self):
		invalidator_thread = MagicMock()
		client_cache = types.SimpleNamespace(invalidator_thread=invalidator_thread)

		with (
			patch.object(frappe, "init") as init,
			patch.object(frappe, "destroy") as destroy,
			patch.object(frappe, "cache", MagicMock()),
			patch.object(frappe, "client_cache", client_cache),
			patch("frappe.tests.utils.sqlite_test_shard.importlib.import_module") as import_module,
		):
			import_module.side_effect = [RuntimeError("requires a connected site"), None]
			preload_modules("test_site", ["frappe.tests.test_a", "frappe.tests.test_b"])

			init.assert_called_once_with("test_site")
			self.assertEqual(
				import_module.call_args_list,
				[call("frappe.tests.test_a"), call("frappe.tests.test_b")],
			)
			destroy.assert_called_once_with()
			invalidator_thread.stop.assert_called_once_with()
			invalidator_thread.pubsub.close.assert_called_once_with()
			invalidator_thread.join.assert_called_once_with()
			self.assertIsNone(frappe.cache)
			self.assertIsNone(frappe.client_cache)

	@patch("frappe.tests.utils.sqlite_test_shard.run_tests")
	def test_module_reuses_prepared_test_state(self, run_tests):
		with (
			patch.object(frappe, "init") as init,
			patch.object(frappe, "destroy") as destroy,
		):
			run_module("test_site", "frappe", "frappe.tests.test_db")

		init.assert_called_once_with("test_site")
		run_tests.assert_called_once_with(
			site="test_site",
			app="frappe",
			module="frappe.tests.test_db",
			skip_before_tests=True,
			preserve_test_records=True,
		)
		destroy.assert_called_once_with()

	@patch("frappe.tests.utils.sqlite_test_shard.multiprocessing.get_context")
	@patch("frappe.tests.utils.sqlite_test_shard.restore_site")
	def test_failed_module_does_not_stop_shard(self, restore_site, get_context):
		processes = [MagicMock(exitcode=0), MagicMock(exitcode=1), MagicMock(exitcode=0)]
		get_context.return_value.Process.side_effect = processes
		snapshot = Path("/tmp/pristine-site")
		site_path = Path("/tmp/sites/test_site")

		failed_modules = run_modules(
			"test_site",
			"frappe",
			["frappe.tests.test_a", "frappe.tests.test_b", "frappe.tests.test_c"],
			snapshot,
			site_path,
		)

		self.assertEqual(failed_modules, ["frappe.tests.test_b"])
		self.assertEqual(
			get_context.return_value.Process.call_args_list,
			[
				call(
					target=run_module,
					args=("test_site", "frappe", "frappe.tests.test_a"),
				),
				call(
					target=run_module,
					args=("test_site", "frappe", "frappe.tests.test_b"),
				),
				call(
					target=run_module,
					args=("test_site", "frappe", "frappe.tests.test_c"),
				),
			],
		)
		self.assertEqual(restore_site.call_args_list, [call(snapshot, site_path)] * 3)
		for process in processes:
			process.start.assert_called_once_with()
			process.join.assert_called_once_with()
