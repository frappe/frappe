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
from frappe.flow.daemon import lifecycle
from frappe.tests import UnitTestCase


class TestDaemonLifecycle(UnitTestCase):
	def setUp(self):
		tmp = TemporaryDirectory()
		self.addCleanup(tmp.cleanup)
		(Path(tmp.name) / "config").mkdir()
		self.enterContext(patch("frappe.utils.synchronization.get_bench_path", return_value=tmp.name))
		self.bench_path = lifecycle.get_bench_path
		self.enterContext(patch.object(lifecycle, "get_bench_path", return_value=tmp.name))
		self.sites = Path(tmp.name).resolve() / "sites"
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
		self.supervised = lifecycle.supervised
		self.enterContext(patch.object(lifecycle, "supervised", return_value=False))
		self.flow_bin = Path(tmp.name) / "env" / "bin" / "flow"
		self.enterContext(patch.object(lifecycle, "_flow_bin", return_value=self.flow_bin))
		self.site = frappe.local.site

	def test_the_template_finds_each_site_and_calls_back_to_the_bench(self):
		site = self.sites / "{site}"
		method = "/api/method/frappe.flow.daemon.callback.callback"
		with (
			patch.object(frappe, "get_common_site_config", return_value=frappe._dict(webserver_port=8001)),
			patch.dict(frappe.local.conf, {"flow_server_url": "https://site.example.com"}),
		):
			self.assertEqual(lifecycle.callback_url(), f"http://127.0.0.1:8001{method}")
			self.assertEqual(
				lifecycle.tenant_template(),
				{
					"token_file": str(site / "site_config.json"),
					"token_key": "flow_server_secret",
					"allowed_roots": [str(site / "public" / "files"), str(self.sites.parent / "apps")],
					"ignore_hidden_files": True,
					"callback_hosts": ["127.0.0.1:8001"],
					"callback_headers": {"X-Frappe-Site-Name": "{site}"},
					"data_dir": str(site / "private" / "flow"),
					"extensions": [str(site / "private" / "flow" / "extensions")],
				},
			)
		bench = frappe._dict(flow_server_url="https://erp.example.com/")
		with patch.object(frappe, "get_common_site_config", return_value=bench):
			self.assertEqual(lifecycle.callback_url(), f"https://erp.example.com{method}")
			self.assertEqual(lifecycle.tenant_template()["callback_hosts"], ["erp.example.com"])

	def test_the_daemon_files_live_in_the_bench_and_each_site(self):
		bench = self.state.parents[1]
		self.assertEqual(self.state_dir(), bench / "sites" / "flow-server")
		self.assertEqual(self.runtime_dir(), bench / "flow-server")
		self.assertEqual(self.log_path(), bench / "logs" / "flow-server.log")
		with (
			patch.object(lifecycle, "get_bench_path", self.bench_path),
			patch.object(lifecycle, "site_data_dir", self.site_data_dir),
		):
			template = json.loads(json.dumps(lifecycle.tenant_template()).replace("{site}", self.site))
			self.assertEqual(template["allowed_roots"][0], str(lifecycle.session_root()))
			self.assertEqual(template["data_dir"], str(lifecycle.site_data_dir()))
			self.assertEqual(template["extensions"], [str(lifecycle.site_extensions_dir())])

	def test_a_site_gets_its_secret_once(self):
		with patch.object(lifecycle, "update_site_config") as config:
			lifecycle.provision_site()
			config.assert_not_called()  # the site already has one
			with patch.dict(frappe.local.conf, {"flow_server_secret": None}):
				lifecycle.provision_site()
		key, secret = config.call_args.args
		self.assertEqual(key, "flow_server_secret")
		self.assertEqual(len(secret), 48)

	def test_flow_sites_are_the_ones_whose_config_holds_a_secret(self):
		for site, config in (
			("a.localhost", '{"flow_server_secret": "s"}'),
			("b.localhost", "{}"),
			("c.localhost", "{"),
		):
			(self.sites / site).mkdir(parents=True)
			(self.sites / site / "site_config.json").write_text(config)
		(self.sites / "assets").mkdir()
		self.assertEqual(lifecycle.flow_sites(), ["a.localhost"])
		self.assertTrue(lifecycle.status().endswith("sites: a.localhost"))

	def test_app_source_prompt_is_only_added_when_an_app_code_tool_is_selected(self):
		self.assertEqual(lifecycle.app_source_prompt([]), "")
		with patch.object(lifecycle, "app_sources", return_value=[("custom_app", Path("/apps/custom"))]):
			prompt = lifecycle.app_source_prompt(["grep"])
		self.assertIn("Use grep", prompt)
		self.assertIn("custom_app: /apps/custom", prompt)

	def test_start_launches_a_scrubbed_server_that_allows_every_sites_extension_tools(self):
		self.install_flow_bin()
		folder = self.sites / "a.localhost" / "private" / "flow" / "extensions"
		folder.mkdir(parents=True)
		other = self.sites / "b.localhost" / "private" / "flow" / "extensions"
		other.mkdir(parents=True)
		(self.sites / "c.localhost" / "private" / "flow").mkdir(parents=True)
		rows = [{"name": "helpdesk_ticket", "description": "Fetch a ticket.", "extension": "helpdesk"}]
		environ = {
			"PATH": "/usr/bin",
			"FLOW_AUTH_TOKEN": "x",
			"FLOW_ALLOWED_ROOTS": "/",
			"OPENAI_API_KEY": "sk",
		}
		with (
			patch.dict(os.environ, environ, clear=True),
			patch.object(lifecycle, "healthy", side_effect=[False, True]),
			patch.object(lifecycle, "extension_tools", return_value=rows) as listing,
			patch.object(subprocess, "Popen", return_value=FakeProcess()) as popen,
			patch.object(
				frappe, "get_common_site_config", return_value=frappe._dict(redis_queue="redis://q")
			),
		):
			lifecycle.start()
			template = lifecycle.tenant_template()
		# one listing per folder that exists, like the daemon loads them
		self.assertCountEqual([c.args[0] for c in listing.call_args_list], [[folder], [other]])
		command, kwargs = popen.call_args.args[0], popen.call_args.kwargs
		self.assertEqual(command[:2], [str(self.flow_bin), "serve"])
		self.assertEqual(  # each site's extensions folder comes from the template
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
				"FLOW_TENANTS": json.dumps(template),
				# the same tool in two sites is allowed once
				"FLOW_POLICY": '{"tool_allowlist": ["read", "grep", "subagent", "suggest_replies", "helpdesk_ticket"]}',
				"FLOW_REDIS_URL": "redis://q",
			},
		)
		self.assertTrue(kwargs["start_new_session"])
		self.assertEqual(kwargs["umask"], 0o077)
		self.assertEqual(lifecycle.pid_file().read_text(), "4242")

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

	def test_failing_steps_warn_without_failing_install_or_migrate(self):
		for hook in (lifecycle.after_install, lifecycle.after_migrate):
			with (
				self.subTest(hook=hook.__name__),
				patch.object(lifecycle, "supervised", self.supervised),
				patch.object(frappe, "get_common_site_config", return_value={"flow_server_manager": "typo"}),
				patch.object(lifecycle, "sync_server_tools", side_effect=RuntimeError("no listing")) as sync,
				patch.object(subprocess, "Popen") as popen,
				patch.object(click, "secho") as secho,
			):
				hook()
			warnings = [call.args[0] for call in secho.call_args_list]
			self.assertIn("flow_server_manager must be local or supervisor", warnings[0])
			# the sync still runs, and warns too
			self.assertTrue(any("no listing" in warning for warning in warnings[1:]))
			popen.assert_not_called()
			sync.assert_called_once()

	def test_migrate_restarts_unless_supervised_and_the_site_has_no_extensions(self):
		for supervised, extensions, restarts in ((False, False, 1), (True, False, 0), (True, True, 1)):
			with (
				self.subTest(supervised=supervised, extensions=extensions),
				patch.object(lifecycle, "supervised", return_value=supervised),
				patch.object(lifecycle, "restart") as restart,
				patch.object(lifecycle, "sync_server_tools") as sync,
			):
				if extensions:
					(self.partition / "extensions").mkdir(parents=True)
				lifecycle.after_migrate()
			self.assertEqual(restart.call_count, restarts)
			sync.assert_called_once()

	def test_entry_points_act_inside_the_global_lock(self):
		for entrypoint, up, steps, result in (
			("ensure_running", True, ["healthy"], False),
			("ensure_running", False, ["healthy", "_restart"], True),
			("start", None, ["_start"], None),
			("stop", None, ["_stop"], None),
			("restart", None, ["_restart"], None),
		):
			with self.subTest(entrypoint=entrypoint, up=up):
				events = []

				@contextmanager
				def locked(name, *, is_global):
					events.append(("enter", name, is_global))
					yield
					events.append(("exit", name, is_global))

				def step(name, value=None):
					def record():
						events.append(name)
						return value

					return record

				with (
					patch.object(lifecycle, "filelock", side_effect=locked),
					patch.object(lifecycle, "healthy", side_effect=step("healthy", up)),
					patch.object(lifecycle, "_start", side_effect=step("_start")),
					patch.object(lifecycle, "_stop", side_effect=step("_stop")),
					patch.object(lifecycle, "_restart", side_effect=step("_restart")),
				):
					self.assertEqual(getattr(lifecycle, entrypoint)(), result)

				self.assertEqual(
					events, [("enter", lifecycle.LOCK, True), *steps, ("exit", lifecycle.LOCK, True)]
				)

	def test_start_cleans_up_a_process_that_never_becomes_healthy(self):
		self.install_flow_bin()
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

	def test_ownership_comes_from_bench_config_not_site_config_or_a_stale_marker(self):
		self.runtime.mkdir(parents=True)
		(self.runtime / "supervised").touch()
		for config, expected in (
			({}, False),
			({"flow_server_manager": "local"}, False),
			({"flow_server_manager": "supervisor"}, True),
		):
			with (
				self.subTest(config=config),
				patch.object(frappe, "get_common_site_config", return_value=frappe._dict(config)),
				patch.dict(
					frappe.local.conf, {"flow_server_manager": "supervisor" if not expected else "local"}
				),
			):
				self.assertEqual(self.supervised(), expected)

	def test_a_supervised_daemon_is_waited_for_but_never_spawned(self):
		# two calls each: once supervisor brings it up, once it never does
		for entrypoint, stops in (("start", 0), ("ensure_running", 0), ("restart", 2)):
			with (
				self.subTest(entrypoint=entrypoint),
				patch.object(lifecycle, "supervised", return_value=True),
				patch.object(lifecycle, "healthy", side_effect=[False, True]) as healthy,
				patch.object(lifecycle.time, "sleep"),
				patch.object(lifecycle, "filelock") as lock,
				patch.object(lifecycle, "_stop") as stop,
				patch.object(lifecycle, "_start") as start,
				patch.object(subprocess, "Popen") as popen,
			):
				self.assertFalse(getattr(lifecycle, entrypoint)())
				self.assertEqual(healthy.call_count, 2)
				with (
					patch.object(lifecycle, "START_TIMEOUT", 0),
					self.assertRaisesRegex(RuntimeError, "did not become ready under supervisor"),
				):
					getattr(lifecycle, entrypoint)()
			# restart stops it for supervisor to start again; only that takes the launch lock
			self.assertEqual(stop.call_count, stops)
			self.assertEqual(lock.call_count, stops)
			start.assert_not_called()
			popen.assert_not_called()

	def test_install_waits_for_supervisor_before_syncing_tools(self):
		self.install_flow_bin()
		events = []
		with (
			patch.object(lifecycle, "supervised", return_value=True),
			patch.object(lifecycle, "_wait_for_supervisor", side_effect=lambda: events.append("ready")),
			patch.object(lifecycle, "sync_server_tools", side_effect=lambda: events.append("sync")),
			patch.object(subprocess, "Popen") as popen,
		):
			lifecycle.keep_alive()
			lifecycle.after_install()
		self.assertEqual(events, ["ready", "sync"])
		popen.assert_not_called()

	def test_serve_becomes_the_daemon_in_the_foreground(self):
		"""With no site to wait for: one moved onto this bench later works on its first request."""
		self.install_flow_bin()
		with (
			patch.dict(os.environ, {"PATH": "/usr/bin", "OPENAI_API_KEY": "sk"}, clear=True),
			patch.object(lifecycle, "_redis_url", return_value=None),
			patch.object(lifecycle, "_stop") as stop,
			patch.object(lifecycle, "supervised", return_value=True),
			patch.object(os, "chdir") as chdir,
			patch.object(os, "umask") as umask,
			patch.object(os, "execve") as execve,
		):
			lifecycle.serve()
		stop.assert_called_once()  # a daemon Flow started before
		command, args, env = execve.call_args.args
		self.assertEqual(command, str(self.flow_bin))
		self.assertEqual(args[:2], [str(self.flow_bin), "serve"])
		self.assertEqual(
			env,
			{
				"PATH": "/usr/bin",
				"FLOW_TENANTS": json.dumps(lifecycle.tenant_template()),
				"FLOW_POLICY": '{"tool_allowlist": ["read", "grep", "subagent", "suggest_replies"]}',
			},
		)
		chdir.assert_called_once_with(self.runtime)
		umask.assert_called_once_with(0o077)
		self.assertEqual(lifecycle.pid_file().read_text(), str(os.getpid()))

	def test_serve_refuses_until_its_manager_claims_the_bench(self):
		with (
			patch.object(lifecycle, "_stop") as stop,
			patch.object(os, "execve") as execve,
			self.assertRaisesRegex(RuntimeError, "set flow_server_manager to supervisor"),
		):
			lifecycle.serve()
		stop.assert_not_called()
		execve.assert_not_called()

		self.install_flow_bin()
		with (
			patch.dict(os.environ, {"FLOW_SERVER_MANAGER": "supervisor"}),
			patch.object(lifecycle, "update_site_config") as update,
			patch.object(lifecycle, "_redis_url", return_value=None),
			patch.object(lifecycle, "_stop"),
			patch.object(os, "chdir"),
			patch.object(os, "umask"),
			patch.object(os, "execve") as execve,
		):
			lifecycle.serve()
		update.assert_called_once_with(
			"flow_server_manager",
			"supervisor",
			site_config_path=str(lifecycle._sites_dir() / "common_site_config.json"),
		)
		execve.assert_called_once()

	def install_flow_bin(self) -> None:
		self.flow_bin.parent.mkdir(parents=True)
		self.flow_bin.touch()


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
