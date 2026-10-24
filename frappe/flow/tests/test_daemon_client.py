# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx

import frappe
from frappe.flow.daemon import lifecycle
from frappe.flow.daemon.client import DaemonClient, DaemonError
from frappe.flow.tools.builtins import sync_builtin_tools
from frappe.tests import IntegrationTestCase, UnitTestCase

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
			(lambda: self.client.rewind("s1", 3), "POST", "/sessions/s1/rewind", {"target_seq": 3}),
			(lambda: self.client.compact("s1"), "POST", "/sessions/s1/compact", None),
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
			(
				lambda: self.client.upload_attachments("s1", [("a.png", b"\x89PNG", "image/png")]),
				"POST",
				"/sessions/s1/attachments",
				None,
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
		self.assertEqual(dict(self.requests[-3].url.params), {"since": "3", "path": "all"})
		upload = self.requests[-1]
		self.assertIn("multipart/form-data", upload.headers["Content-Type"])
		self.assertIn(b'filename="a.png"', upload.content)
		self.assertIn(b"image/png", upload.content)

	def test_failures_become_daemon_errors_that_never_echo_the_input_or_token(self):
		refusal = "callback_url host 'x' is not allowed by server policy"
		invalid = {
			"type": "extra_forbidden",
			"loc": ["body", "bogus"],
			"msg": "Extra inputs are not permitted",
			"input": {"api_key": "sk-secret", "bogus": 1},
		}
		for status, detail, kept in (
			(400, refusal, refusal),
			(422, [invalid], [{"loc": ["body", "bogus"], "msg": "Extra inputs are not permitted"}]),
		):
			with self.subTest(status=status):
				self.reply = httpx.Response(status, json={"detail": detail})
				with self.assertRaises(DaemonError) as caught:
					self.client.create_session({"api_key": "sk-secret", "bogus": 1})
				self.assertEqual((caught.exception.status, caught.exception.detail), (status, kept))
				self.assertIn(str(status), str(caught.exception))
				self.assertNotIn("sk-secret", str(caught.exception))

		with DaemonClient("/nowhere/flow.sock", TOKEN) as client:
			with self.assertRaises(DaemonError) as caught:
				client.healthz()
		self.assertIsNone(caught.exception.status)
		self.assertIn("unreachable", str(caught.exception))
		self.assertNotIn(TOKEN, str(caught.exception))

	def test_a_client_sends_only_the_site_and_secret_it_has(self):
		with patch.dict(frappe.local.conf, {"flow_server_secret": None}):
			with self.assertRaisesRegex(DaemonError, "not provisioned"):
				DaemonClient.for_site()
		with patch.dict(frappe.local.conf, {"flow_server_secret": TOKEN}), DaemonClient.for_site() as client:
			self.assertEqual(client._http.headers["X-Flow-Site"], frappe.local.site)
			self.assertEqual(client._http.headers["Authorization"], f"Bearer {TOKEN}")
		self.assertNotIn("X-Flow-Site", self.client._http.headers)
		with DaemonClient(
			"/nowhere/flow.sock", transport=httpx.MockTransport(lambda r: self.reply)
		) as client:
			client.healthz()
		self.assertNotIn("Authorization", client._http.headers)


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
		sites = root / "sites"
		cls.enterClassContext(patch.object(lifecycle, "state_dir", return_value=root / "state"))
		cls.enterClassContext(patch.object(lifecycle, "_sites_dir", return_value=sites))
		site_files = sites / frappe.local.site / "public" / "files"
		cls.enterClassContext(patch.object(lifecycle, "session_root", return_value=site_files))
		cls.enterClassContext(patch.object(lifecycle, "runtime_dir", return_value=root))
		cls.enterClassContext(patch.object(lifecycle, "log_path", return_value=root / "flow-server.log"))
		cls.enterClassContext(patch.object(lifecycle, "_redis_url", return_value=None))
		# the real lock file lives in the bench's config folder
		cls.enterClassContext(patch.object(lifecycle, "filelock"))
		cls.enterClassContext(patch.dict(frappe.local.conf, {"flow_server_secret": TOKEN}))
		for site, secret in ((frappe.local.site, TOKEN), ("other.localhost", "other-token")):
			(sites / site).mkdir(parents=True)
			(sites / site / "site_config.json").write_text(json.dumps({"flow_server_secret": secret}))
		lifecycle.start()
		cls.addClassCleanup(lifecycle.stop)
		cls.other = DaemonClient(str(lifecycle.socket_path()), "other-token", site="other.localhost")
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
		with patch("frappe.flow.lib.model.resolve_provider_credentials", return_value={}):
			config = session.server_config()
		return {**config, "session_id": session_id, "model": "mock"}

	def test_each_site_reaches_only_its_own_sessions_with_its_own_secret(self):
		self.assertEqual(self.client.healthz(), {"ok": True})
		self.assertIn(frappe.local.site, lifecycle.status())
		self.assertIn("other.localhost", lifecycle.status())
		self.client.create_session(self.config("partitioned"))
		self.assertEqual(self.client.get_session("partitioned")["session_id"], "partitioned")
		with self.assertRaises(DaemonError) as caught:
			self.other.get_session("partitioned")
		self.assertEqual(caught.exception.status, 404)
		for token, site in (("wrong", frappe.local.site), (TOKEN, None), ("other-token", frappe.local.site)):
			with self.subTest(token=token, site=site):
				with DaemonClient(str(lifecycle.socket_path()), token, site=site) as stranger:
					with self.assertRaises(DaemonError) as caught:
						stranger.get_session("nothing")
				self.assertEqual(caught.exception.status, 401)

	def test_a_session_asking_past_the_server_policy_is_refused(self):
		for change, detail in (
			({"tools": ["bash"]}, "not allowed by server policy"),
			({"tools": ["write"]}, "not allowed by server policy"),
			({"callback_url": "http://evil.example.com/hook"}, "callback_url"),
		):
			with self.subTest(change=change):
				with self.assertRaises(DaemonError) as caught:
					self.client.create_session({**self.config("policy-probe"), **change})
				self.assertEqual(caught.exception.status, 400)
				self.assertIn(detail, caught.exception.detail)

	def test_a_session_hides_its_credentials_and_runs_until_deleted(self):
		created = self.client.create_session(self.config("turns"))
		self.assertEqual(created["session_id"], "turns")
		self.assertEqual(created["config"]["api_key"], "***")
		self.assertEqual(created["config"]["callback_token"], "***")
		self.assertEqual(created["config"]["tools"], [])
		fetched = self.client.get_session("turns")
		self.assertEqual(fetched["config"]["api_key"], "***")
		self.assertNotIn("sk-live", json.dumps(fetched))
		self.assertNotIn(TOKEN, json.dumps(fetched))
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
