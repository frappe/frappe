# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import frappe
import httpx
from frappe.tests import IntegrationTestCase, UnitTestCase

from flow.daemon import lifecycle
from flow.daemon.client import DaemonClient, DaemonError
from flow.tools.builtins import sync_builtin_tools

TOKEN = "site-token-abc"


class TestDaemonClient(UnitTestCase):
	def setUp(self):
		self.requests: list[httpx.Request] = []
		self.reply: httpx.Response = httpx.Response(200, json={"ok": True})

		def handle(request: httpx.Request) -> httpx.Response:
			self.requests.append(request)
			return self.reply

		self.client = DaemonClient("/nowhere/flow.sock", TOKEN, transport=httpx.MockTransport(handle))
		self.addCleanup(self.client.close)

	def test_every_verb_hits_its_route_with_the_bearer(self):
		calls = [
			(lambda: self.client.healthz(), "GET", "/healthz", None),
			(lambda: self.client.reload_tenants(), "POST", "/tenants/reload", None),
			(lambda: self.client.create_session({"model": "mock"}), "POST", "/sessions", {"model": "mock"}),
			(lambda: self.client.get_session("s1"), "GET", "/sessions/s1", None),
			(lambda: self.client.delete_session("s1"), "DELETE", "/sessions/s1", None),
			(
				lambda: self.client.run("s1", "hi", attachments=["a1"]),
				"POST",
				"/sessions/s1/run",
				{"message": "hi", "attachments": ["a1"]},
			),
			(
				lambda: self.client.resume("s1", {"c1": "Approve"}, approval_seq=7),
				"POST",
				"/sessions/s1/resume",
				{"approval_seq": 7, "answers": {"c1": "Approve"}},
			),
			(lambda: self.client.abort("s1"), "POST", "/sessions/s1/abort", None),
			(lambda: self.client.cancel_pending("s1"), "POST", "/sessions/s1/cancel_pending", None),
			(
				lambda: self.client.set_model("s1", "openai/gpt-5", api_key="k", api_base="https://b"),
				"POST",
				"/sessions/s1/model",
				{"model": "openai/gpt-5", "api_key": "k", "api_base": "https://b", "reasoning_effort": None},
			),
			(
				lambda: self.client.set_model("s1", "openai/gpt-5", model_params={"route": "x"}),
				"POST",
				"/sessions/s1/model",
				{
					"model": "openai/gpt-5",
					"api_key": None,
					"api_base": None,
					"reasoning_effort": None,
					"model_params": {"route": "x"},
				},
			),
			(
				lambda: self.client.patch_config("s1", title="T"),
				"PATCH",
				"/sessions/s1/config",
				{"title": "T", "auto_approve": None},
			),
			(
				lambda: self.client.patch_config(
					"s1", client_tools=[{"function": {"name": "read"}}], confirm_tools=["read"]
				),
				"PATCH",
				"/sessions/s1/config",
				{
					"title": None,
					"auto_approve": None,
					"client_tools": [{"function": {"name": "read"}}],
					"confirm_tools": ["read"],
				},
			),
			(
				lambda: self.client.patch_config("s1", tools=["grep"]),
				"PATCH",
				"/sessions/s1/config",
				{
					"title": None,
					"auto_approve": None,
					"tools": ["grep"],
				},
			),
			(lambda: self.client.entries("s1", since=3, path="all"), "GET", "/sessions/s1/entries", None),
			(
				lambda: self.client.cleanup_attachments("s1", ["a1", "a2"]),
				"DELETE",
				"/sessions/s1/attachments",
				{"attachments": ["a1", "a2"]},
			),
		]
		for call, method, path, body in calls:
			with self.subTest(path=path):
				self.assertEqual(call(), {"ok": True})
				request = self.requests[-1]
				self.assertEqual((request.method, request.url.path), (method, path))
				self.assertEqual(request.headers["Authorization"], f"Bearer {TOKEN}")
				if body is not None:
					self.assertEqual(json.loads(request.content), body)
		self.assertEqual(dict(self.requests[-2].url.params), {"since": "3", "path": "all"})

	def test_uploads_send_multipart_files(self):
		self.client.upload_attachments("s1", [("a.png", b"\x89PNG", "image/png")])
		request = self.requests[-1]
		self.assertEqual(request.url.path, "/sessions/s1/attachments")
		self.assertIn("multipart/form-data", request.headers["Content-Type"])
		self.assertIn(b'filename="a.png"', request.content)
		self.assertIn(b"image/png", request.content)

	def test_refusals_become_daemon_errors_with_the_daemons_detail(self):
		self.reply = httpx.Response(
			400, json={"detail": "callback_url host 'x' is not allowed by server policy"}
		)
		with self.assertRaises(DaemonError) as caught:
			self.client.create_session({})
		self.assertEqual(caught.exception.status, 400)
		self.assertEqual(caught.exception.detail, "callback_url host 'x' is not allowed by server policy")
		self.assertIn("400", str(caught.exception))

	def test_validation_errors_keep_the_field_and_message_but_never_the_input(self):
		self.reply = httpx.Response(
			422,
			json={
				"detail": [
					{
						"type": "extra_forbidden",
						"loc": ["body", "bogus"],
						"msg": "Extra inputs are not permitted",
						"input": {"api_key": "sk-secret", "bogus": 1},
					}
				]
			},
		)
		with self.assertRaises(DaemonError) as caught:
			self.client.create_session({"api_key": "sk-secret", "bogus": 1})
		self.assertEqual(caught.exception.status, 422)
		self.assertEqual(
			caught.exception.detail, [{"loc": ["body", "bogus"], "msg": "Extra inputs are not permitted"}]
		)
		self.assertNotIn("sk-secret", str(caught.exception))

	def test_an_unreachable_daemon_is_an_error_without_a_status(self):
		with DaemonClient("/nowhere/flow.sock", TOKEN) as client:
			with self.assertRaises(DaemonError) as caught:
				client.healthz()
		self.assertIsNone(caught.exception.status)
		self.assertIn("unreachable", str(caught.exception))
		self.assertNotIn(TOKEN, str(caught.exception))

	def test_a_client_without_a_token_sends_no_authorization(self):
		with DaemonClient(
			"/nowhere/flow.sock", transport=httpx.MockTransport(lambda r: self.reply)
		) as client:
			client.healthz()
		self.assertNotIn("Authorization", client._http.headers)

	def test_for_site_needs_a_provisioned_site(self):
		with patch.dict(frappe.local.conf, {"flow_server_secret": None}):
			with self.assertRaisesRegex(DaemonError, "not provisioned"):
				DaemonClient.for_site()


class TestLiveDaemon(IntegrationTestCase):
	"""Every verb against a real daemon in the deployed profile, started and stopped through
	the lifecycle module with its paths pointed at a temporary directory."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not lifecycle._flow_bin().exists():
			raise unittest.SkipTest("the flow server is not installed in this environment")
		tmp = TemporaryDirectory()
		cls.addClassCleanup(tmp.cleanup)
		root = Path(tmp.name)
		cls.enterClassContext(patch.object(lifecycle, "state_dir", return_value=root / "state"))
		cls.enterClassContext(patch.object(lifecycle, "site_data_dir", return_value=root / "site"))
		cls.enterClassContext(patch.object(lifecycle, "runtime_dir", return_value=root))
		cls.enterClassContext(patch.object(lifecycle, "log_path", return_value=root / "flow-server.log"))
		cls.enterClassContext(patch.object(lifecycle, "_redis_url", return_value=None))
		cls.enterClassContext(patch.dict(frappe.local.conf, {"flow_server_secret": TOKEN}))
		lifecycle.provision_site()
		lifecycle._edit_tenants(
			lambda tenants: tenants.__setitem__(
				"other.localhost", {"token": "other-token", "allowed_roots": [tmp.name], "callback_hosts": []}
			)
		)
		lifecycle.start()
		cls.addClassCleanup(lifecycle.stop)
		cls.other = DaemonClient(str(lifecycle.socket_path()), "other-token")
		cls.addClassCleanup(cls.other.close)

	def setUp(self):
		sync_builtin_tools()
		self.client = DaemonClient.for_site()
		self.addCleanup(self.client.close)
		self.model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Live Mock",
				"model_id": "openai/gpt-4o-mini",
				"api_key": "sk-live",
				"enabled": 1,
			}
		).insert()
		self.agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Live Agent",
				"model": self.model.name,
				"instructions": "Reply briefly.",
				"tools": [{"tool": "read_records"}, {"tool": "execute"}],
				"enabled": 1,
			}
		).insert()

	def tearDown(self):
		frappe.db.rollback()

	def config(self, session_id: str) -> dict:
		"""The real config, pointed at the daemon's keyless mock model."""
		session = frappe.get_doc(
			{"doctype": "Flow Session", "agent": self.agent.name, "title": "Live test"}
		).insert()
		with patch("flow.lib.model.resolve_provider_credentials", return_value={}):
			config = session.server_config()
		return {**config, "session_id": session_id, "model": "mock"}

	def test_the_daemon_answers_and_serves_both_sites(self):
		self.assertEqual(self.client.healthz(), {"ok": True})
		self.assertIn(frappe.local.site, lifecycle.status())
		self.assertIn("other.localhost", lifecycle.status())

	def test_a_wrong_token_is_401(self):
		with DaemonClient(str(lifecycle.socket_path()), "wrong") as stranger:
			with self.assertRaises(DaemonError) as caught:
				stranger.get_session("nothing")
		self.assertEqual(caught.exception.status, 401)

	def test_the_daemons_own_tools_are_refused_by_policy(self):
		for tools in (["bash"], ["write"]):
			with self.subTest(tools=tools), self.assertRaises(DaemonError) as caught:
				self.client.create_session({**self.config("policy-probe"), "tools": tools})
			self.assertEqual(caught.exception.status, 400)
			self.assertIn("not allowed by server policy", caught.exception.detail)

	def test_a_foreign_callback_host_is_refused(self):
		config = {**self.config("callback-probe"), "callback_url": "http://evil.example.com/hook"}
		with self.assertRaises(DaemonError) as caught:
			self.client.create_session(config)
		self.assertEqual(caught.exception.status, 400)
		self.assertIn("callback_url", caught.exception.detail)

	def test_inline_credentials_are_accepted_and_come_back_redacted(self):
		created = self.client.create_session(self.config("redaction"))
		self.assertEqual(created["session_id"], "redaction")
		self.assertEqual(created["config"]["api_key"], "***")
		self.assertEqual(created["config"]["callback_token"], "***")
		self.assertEqual(created["config"]["tools"], [])
		fetched = self.client.get_session("redaction")
		self.assertEqual(fetched["config"]["api_key"], "***")
		self.assertNotIn("sk-live", json.dumps(fetched))
		self.assertNotIn(TOKEN, json.dumps(fetched))

	def test_sessions_are_partitioned_by_site(self):
		self.client.create_session(self.config("partitioned"))
		self.assertEqual(self.client.get_session("partitioned")["session_id"], "partitioned")
		with self.assertRaises(DaemonError) as caught:
			self.other.get_session("partitioned")
		self.assertEqual(caught.exception.status, 404)

	def test_a_run_returns_immediately_and_finishes_in_the_log(self):
		self.client.create_session(self.config("turns"))
		self.assertEqual(self.client.run("turns", "hello there"), {"status": "started"})
		for _ in range(100):
			if not self.client.get_session("turns")["running"]:
				break
			time.sleep(0.01)
		else:
			self.fail("daemon run did not finish")
		self.assertEqual(self.client.get_session("turns")["title"], "Live test")
		entries = self.client.entries("turns")["entries"]
		types = [entry["type"] for entry in entries]
		self.assertIn("user_message", types)
		self.assertIn("assistant_message", types)
		self.assertEqual(
			next(row for row in entries if row["type"] == "assistant_message")["content"],
			[{"type": "text", "text": "Mock reply to: hello there"}],
		)
		self.assertEqual(self.client.patch_config("turns", title="Renamed")["config"]["title"], "Renamed")
		self.assertEqual(self.client.delete_session("turns"), {"status": "deleted"})
		with self.assertRaises(DaemonError) as caught:
			self.client.get_session("turns")
		self.assertEqual(caught.exception.status, 404)
