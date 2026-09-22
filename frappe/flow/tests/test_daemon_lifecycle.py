# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import click
import frappe
from frappe.tests import UnitTestCase

from flow.daemon import lifecycle


class TestDaemonLifecycle(UnitTestCase):
	def setUp(self):
		tmp = TemporaryDirectory()
		self.addCleanup(tmp.cleanup)
		self.state = Path(tmp.name) / "sites" / "flow-server"
		self.runtime = Path(tmp.name) / "flow-server"
		self.log = Path(tmp.name) / "logs" / "flow-server.log"
		self.log.parent.mkdir()
		self.partition = Path(tmp.name) / "site" / "private" / "flow"
		self.state_dir = lifecycle.state_dir
		self.runtime_dir = lifecycle.runtime_dir
		self.log_path = lifecycle.log_path
		self.site_data_dir = lifecycle.site_data_dir
		self.enterContext(patch.object(lifecycle, "site_data_dir", return_value=self.partition))
		self.enterContext(patch.object(lifecycle, "state_dir", return_value=self.state))
		self.enterContext(patch.object(lifecycle, "runtime_dir", return_value=self.runtime))
		self.enterContext(patch.object(lifecycle, "log_path", return_value=self.log))
		self.enterContext(patch.dict(frappe.local.conf, {"flow_server_secret": "site-token"}))
		self.enterContext(patch.object(lifecycle, "healthy", return_value=False))
		self.flow_bin = Path(tmp.name) / "env" / "bin" / "flow"
		self.enterContext(patch.object(lifecycle, "_flow_bin", return_value=self.flow_bin))
		self.site = frappe.local.site

	def test_callbacks_go_to_the_local_web_server_unless_overridden(self):
		method = "/api/method/flow.daemon.callback.callback"
		with patch.dict(frappe.local.conf, {"flow_server_url": None, "webserver_port": 8001}):
			self.assertEqual(lifecycle.callback_url(), f"http://127.0.0.1:8001{method}")
			self.assertEqual(lifecycle.callback_host(), "127.0.0.1:8001")
		with patch.dict(frappe.local.conf, {"flow_server_url": "https://erp.example.com/"}):
			self.assertEqual(lifecycle.callback_url(), f"https://erp.example.com{method}")
			self.assertEqual(lifecycle.callback_host(), "erp.example.com")
		self.assertEqual(lifecycle.callback_headers(), {"X-Frappe-Site-Name": self.site})

	def test_durable_state_uses_the_sites_directory(self):
		bench = self.state.parents[1]
		with patch.object(lifecycle, "get_bench_path", return_value=str(bench)):
			self.assertEqual(self.state_dir(), bench / "sites" / "flow-server")
			self.assertEqual(self.runtime_dir(), bench / "flow-server")
			self.assertEqual(self.log_path(), bench / "logs" / "flow-server.log")

	def test_provision_site_writes_secret_and_tenants_entry(self):
		with (
			patch.dict(frappe.local.conf, {"flow_server_secret": None}),
			patch.object(
				lifecycle, "update_site_config", side_effect=frappe.local.conf.__setitem__
			) as config,
		):
			lifecycle.provision_site()
		key, secret = config.call_args.args
		self.assertEqual(key, "flow_server_secret")
		self.assertEqual(
			self.tenants()[self.site],
			{
				"token": secret,
				"allowed_roots": [str(root) for root in lifecycle.allowed_roots()],
				"ignore_hidden_files": True,
				"callback_hosts": [lifecycle.callback_host()],
				"data_dir": str(self.partition),
				"extensions": [str(self.partition / "extensions")],
			},
		)
		self.assertEqual((self.state / "tenants.json").stat().st_mode & 0o777, 0o600)

	def test_provision_site_keeps_an_existing_secret(self):
		with patch.object(lifecycle, "update_site_config") as config:
			lifecycle.provision_site()
			lifecycle.provision_site()
		config.assert_not_called()
		self.assertEqual(self.tenants()[self.site]["token"], "site-token")

	def test_session_root_is_the_sites_public_files_folder(self):
		root = lifecycle.session_root()
		self.assertEqual(root, Path(frappe.get_site_path("public", "files")).resolve())
		self.assertTrue(root.is_absolute())

	def test_site_data_dir_is_inside_the_site(self):
		self.assertEqual(self.site_data_dir(), Path(frappe.get_site_path("private", "flow")).resolve())

	def test_allowed_roots_are_the_site_files_and_the_whole_bench_apps_dir(self):
		bench = self.state.parents[1]
		with patch.object(lifecycle, "get_bench_path", return_value=str(bench)):
			self.assertEqual(lifecycle.allowed_roots(), (lifecycle.session_root(), bench.resolve() / "apps"))

	def test_app_source_prompt_is_only_added_when_an_app_code_tool_is_selected(self):
		self.assertEqual(lifecycle.app_source_prompt([]), "")
		with patch.object(lifecycle, "app_sources", return_value=[("custom_app", Path("/apps/custom"))]):
			prompt = lifecycle.app_source_prompt(["grep"])
		self.assertIn("Use grep", prompt)
		self.assertIn("custom_app: /apps/custom", prompt)

	def test_remove_site_drops_the_entry_and_the_daemon_data(self):
		self.partition.mkdir(parents=True)
		lifecycle.provision_site()
		lifecycle._edit_tenants(lambda t: t.__setitem__("other.localhost", {"token": "t2"}))
		with (
			patch.object(lifecycle, "reload_tenants", return_value=True) as reload,
			patch.object(lifecycle, "stop") as stop,
		):
			lifecycle.remove_site()
		self.assertEqual(list(self.tenants()), ["other.localhost"])
		self.assertFalse(self.partition.exists())
		reload.assert_called_once_with("site-token")
		stop.assert_not_called()

	def test_remove_site_restarts_when_tenant_reload_fails(self):
		lifecycle.provision_site()
		lifecycle._edit_tenants(lambda t: t.__setitem__("other.localhost", {"token": "t2"}))
		with (
			patch.object(lifecycle, "reload_tenants", return_value=False),
			patch.object(lifecycle, "restart") as restart,
		):
			lifecycle.remove_site()
		restart.assert_called_once()

	def test_removing_the_last_site_stops_the_daemon(self):
		lifecycle.provision_site()
		with patch.object(lifecycle, "stop") as stop:
			lifecycle.remove_site()
		self.assertEqual(self.tenants(), {})
		stop.assert_called_once()

	def test_start_passes_a_scrubbed_environment(self):
		self.install_flow_bin()
		lifecycle.provision_site()
		environ = {
			"PATH": "/usr/bin",
			"FLOW_AUTH_TOKEN": "x",
			"FLOW_ALLOWED_ROOTS": "/",
			"OPENAI_API_KEY": "sk",
		}
		with (
			patch.dict(os.environ, environ, clear=True),
			patch.object(lifecycle, "healthy", side_effect=[False, True]),
			patch.object(subprocess, "Popen", return_value=FakeProcess()) as popen,
			patch.object(
				frappe, "get_common_site_config", return_value=frappe._dict(redis_queue="redis://q")
			),
		):
			lifecycle.start()
		command, kwargs = popen.call_args.args[0], popen.call_args.kwargs
		self.assertEqual(command[:2], [str(self.flow_bin), "serve"])
		self.assertEqual(
			command[2:],
			[
				"--uds",
				str(self.runtime / "flow.sock"),
				"--data-dir",
				str(self.state / "data"),
				"--profile",
				"deployed",
			],
		)
		self.assertEqual(
			kwargs["env"],
			{
				"PATH": "/usr/bin",
				"FLOW_TENANTS_FILE": str(self.state / "tenants.json"),
				"FLOW_POLICY": '{"tool_allowlist": ["read_file", "grep", "subagent"]}',
				"FLOW_REDIS_URL": "redis://q",
			},
		)
		self.assertTrue(kwargs["start_new_session"])
		self.assertEqual(kwargs["umask"], 0o077)
		self.assertEqual(lifecycle.pid_file().read_text(), "4242")

	def test_start_allows_the_tools_of_every_sites_extensions_folder(self):
		self.install_flow_bin()
		lifecycle.provision_site()
		folder = self.partition / "extensions"
		folder.mkdir(parents=True)
		other = self.partition.parent / "other" / "extensions"
		other.mkdir(parents=True)
		lifecycle._edit_tenants(
			lambda tenants: tenants.__setitem__("other", {"extensions": [str(other), "/nowhere"]})
		)
		rows = [{"name": "helpdesk_ticket", "description": "Fetch a ticket.", "extension": "helpdesk"}]
		with (
			patch.object(lifecycle, "healthy", side_effect=[False, True]),
			patch.object(lifecycle, "extension_tools", return_value=rows) as listing,
			patch.object(subprocess, "Popen", return_value=FakeProcess()) as popen,
		):
			lifecycle.start()
		# one listing per folder that exists, like the daemon loads them
		self.assertCountEqual([c.args[0] for c in listing.call_args_list], [[folder], [other]])
		command, kwargs = popen.call_args.args[0], popen.call_args.kwargs
		self.assertNotIn("--extension", command)  # each site's folder comes from its tenants entry
		self.assertEqual(  # the same tool in two sites is allowed once
			kwargs["env"]["FLOW_POLICY"],
			'{"tool_allowlist": ["read_file", "grep", "subagent", "helpdesk_ticket"]}',
		)

	def test_extension_tools_runs_the_harness_listing(self):
		listed = subprocess.CompletedProcess([], 0, stdout='{"tools": [{"name": "hello"}]}', stderr="")
		with patch.object(subprocess, "run", return_value=listed) as run:
			self.assertEqual(lifecycle.extension_tools([Path("/ext")]), [{"name": "hello"}])
		self.assertEqual(run.call_args.args[0], [str(self.flow_bin), "extension-tools", "/ext"])
		self.assertEqual(lifecycle.extension_tools([]), [])

		failed = subprocess.CompletedProcess([], 1, stdout="", stderr="boom")
		with (
			patch.object(subprocess, "run", return_value=failed),
			patch.object(click, "secho") as secho,
			self.assertRaisesRegex(RuntimeError, "extension-tools failed"),
		):
			lifecycle.extension_tools([Path("/ext")])
		self.assertEqual(secho.call_args.args[0], "boom")

	def test_migrate_warns_when_the_tool_sync_fails(self):
		with (
			patch.object(lifecycle, "restart"),
			patch.object(lifecycle, "sync_server_tools", side_effect=RuntimeError("no listing")),
			patch.object(click, "secho") as secho,
		):
			lifecycle.after_migrate()
		self.assertIn("no listing", secho.call_args_list[0].args[0])

	def test_start_refuses_without_a_provisioned_site(self):
		self.install_flow_bin()
		with self.assertRaisesRegex(RuntimeError, "no site is provisioned"):
			lifecycle.start()

	def test_ensure_running_reports_whether_it_started_the_daemon(self):
		with patch.object(lifecycle, "_restart") as restart:
			with patch.object(lifecycle, "healthy", return_value=True):
				self.assertFalse(lifecycle.ensure_running())
			restart.assert_not_called()
			with patch.object(lifecycle, "healthy", return_value=False):
				self.assertTrue(lifecycle.ensure_running())
			restart.assert_called_once()

	def test_ensure_running_checks_health_inside_the_global_lock(self):
		events = []

		@contextmanager
		def locked(name, *, is_global):
			events.append(("enter", name, is_global))
			yield
			events.append(("exit", name, is_global))

		def healthy():
			events.append("healthy")
			return True

		with (
			patch.object(lifecycle, "filelock", side_effect=locked),
			patch.object(lifecycle, "healthy", side_effect=healthy),
		):
			lifecycle.ensure_running()

		self.assertEqual(
			events,
			[("enter", lifecycle.LOCK, True), "healthy", ("exit", lifecycle.LOCK, True)],
		)

	def test_mutating_lifecycle_entry_points_take_the_global_lock(self):
		for entrypoint, operation in (("start", "_start"), ("stop", "_stop"), ("restart", "_restart")):
			with self.subTest(entrypoint=entrypoint):
				events = []

				@contextmanager
				def locked(name, *, is_global):
					events.append(("enter", name, is_global))
					yield
					events.append(("exit", name, is_global))

				def run_operation():
					events.append(operation)

				with (
					patch.object(lifecycle, "filelock", side_effect=locked),
					patch.object(lifecycle, operation, side_effect=run_operation),
				):
					getattr(lifecycle, entrypoint)()

				self.assertEqual(
					events,
					[("enter", lifecycle.LOCK, True), operation, ("exit", lifecycle.LOCK, True)],
				)

	def test_start_cleans_up_a_process_that_never_becomes_healthy(self):
		self.install_flow_bin()
		lifecycle.provision_site()
		process = FakeProcess()
		with (
			patch.object(lifecycle, "START_TIMEOUT", 0),
			patch.object(lifecycle, "healthy", return_value=False),
			patch.object(lifecycle, "_redis_url", return_value=None),
			patch.object(subprocess, "Popen", return_value=process),
			self.assertRaisesRegex(RuntimeError, "did not start"),
		):
			lifecycle.start()

		self.assertTrue(process.terminated)
		self.assertTrue(process.waited)
		self.assertFalse(lifecycle.pid_file().exists())

	def test_stop_ignores_a_pid_that_is_not_the_daemon(self):
		self.runtime.mkdir(parents=True)
		lifecycle.pid_file().write_text(str(os.getpid()))
		with patch.object(os, "kill") as kill:
			lifecycle.stop()
		kill.assert_not_called()
		self.assertFalse(lifecycle.pid_file().exists())

	def test_keep_alive_restarts_a_dead_daemon_only_once_the_harness_is_installed(self):
		with patch.object(lifecycle, "ensure_running") as ensure_running:
			lifecycle.keep_alive()
			ensure_running.assert_not_called()
			self.install_flow_bin()
			lifecycle.keep_alive()
			ensure_running.assert_called_once()

	def install_flow_bin(self) -> None:
		self.flow_bin.parent.mkdir(parents=True)
		self.flow_bin.touch()

	def tenants(self) -> dict:
		return json.loads((self.state / "tenants.json").read_text())


class FakeProcess:
	pid = 4242

	def __init__(self):
		self.terminated = False
		self.waited = False

	def poll(self):
		return None

	def terminate(self):
		self.terminated = True

	def wait(self, timeout=None):
		self.waited = True
		return 0
