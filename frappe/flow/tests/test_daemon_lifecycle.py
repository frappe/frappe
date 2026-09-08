# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

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
		self.state_dir = lifecycle.state_dir
		self.runtime_dir = lifecycle.runtime_dir
		self.log_path = lifecycle.log_path
		self.enterContext(patch.object(lifecycle, "state_dir", return_value=self.state))
		self.enterContext(patch.object(lifecycle, "runtime_dir", return_value=self.runtime))
		self.enterContext(patch.object(lifecycle, "log_path", return_value=self.log))
		self.enterContext(patch.dict(frappe.local.conf, {"flow_server_secret": "site-token"}))
		self.enterContext(patch.object(lifecycle, "healthy", return_value=False))
		self.flow_bin = Path(tmp.name) / "env" / "bin" / "flow"
		self.enterContext(patch.object(lifecycle, "_flow_bin", return_value=self.flow_bin))
		self.site = frappe.local.site

	def test_site_url_prefers_the_explicit_override(self):
		with patch.dict(frappe.local.conf, {"flow_server_url": "https://erp.example.com/"}):
			self.assertEqual(lifecycle.site_url(), "https://erp.example.com")
			self.assertEqual(lifecycle.callback_host(), "erp.example.com")
		with patch.dict(frappe.local.conf, {"flow_server_url": None, "host_name": "erp.example.com:8443"}):
			self.assertEqual(lifecycle.site_url(), "http://erp.example.com:8443")
			self.assertEqual(lifecycle.callback_host(), "erp.example.com:8443")

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
				"allowed_roots": [str(lifecycle.session_root())],
				"callback_hosts": [lifecycle.callback_host()],
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

	def test_remove_site_drops_the_entry_and_the_daemon_data(self):
		partition = self.state / "data" / "tenants" / self.site
		partition.mkdir(parents=True)
		lifecycle.provision_site()
		lifecycle._edit_tenants(lambda t: t.__setitem__("other.localhost", {"token": "t2"}))
		with (
			patch.object(lifecycle, "reload_tenants", return_value=True) as reload,
			patch.object(lifecycle, "stop") as stop,
		):
			lifecycle.remove_site()
		self.assertEqual(list(self.tenants()), ["other.localhost"])
		self.assertFalse(partition.exists())
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
				"FLOW_POLICY": '{"tool_allowlist": []}',
				"FLOW_REDIS_URL": "redis://q",
			},
		)
		self.assertTrue(kwargs["start_new_session"])
		self.assertEqual(kwargs["umask"], 0o077)
		self.assertEqual(lifecycle.pid_file().read_text(), "4242")

	def test_start_refuses_without_a_provisioned_site(self):
		self.install_flow_bin()
		with self.assertRaisesRegex(RuntimeError, "no site is provisioned"):
			lifecycle.start()

	def test_stop_ignores_a_pid_that_is_not_the_daemon(self):
		self.runtime.mkdir(parents=True)
		lifecycle.pid_file().write_text(str(os.getpid()))
		with patch.object(os, "kill") as kill:
			lifecycle.stop()
		kill.assert_not_called()
		self.assertFalse(lifecycle.pid_file().exists())

	def test_keep_alive_restarts_a_dead_daemon_only_once_the_harness_is_installed(self):
		with patch.object(lifecycle, "restart") as restart:
			lifecycle.keep_alive()
			restart.assert_not_called()
			self.install_flow_bin()
			lifecycle.keep_alive()
			restart.assert_called_once()

	def install_flow_bin(self) -> None:
		self.flow_bin.parent.mkdir(parents=True)
		self.flow_bin.touch()

	def tenants(self) -> dict:
		return json.loads((self.state / "tenants.json").read_text())


class FakeProcess:
	pid = 4242

	def poll(self):
		return None
