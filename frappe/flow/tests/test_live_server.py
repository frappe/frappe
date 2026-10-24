# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""A real flow server with the mock model, for tests that round-trip through it."""

import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import frappe
from frappe.flow.daemon import lifecycle
from frappe.flow.daemon.client import DaemonClient
from frappe.flow.doctype.flow_session.flow_session import FlowSession
from frappe.flow.tools.builtins import sync_builtin_tools
from frappe.tests import IntegrationTestCase

TOKEN = "site-token-live"


class LiveServerCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not lifecycle._flow_bin().exists():
			raise unittest.SkipTest("the flow server is not installed in this environment")
		tmp = TemporaryDirectory()
		cls.addClassCleanup(tmp.cleanup)
		root = Path(tmp.name)
		site = root / "sites" / frappe.local.site
		cls.enterClassContext(patch.object(lifecycle, "state_dir", return_value=root / "state"))
		cls.enterClassContext(patch.object(lifecycle, "_sites_dir", return_value=root / "sites"))
		cls.enterClassContext(patch.object(lifecycle, "session_root", return_value=site / "public" / "files"))
		cls.enterClassContext(patch.object(lifecycle, "runtime_dir", return_value=root))
		cls.enterClassContext(patch.object(lifecycle, "log_path", return_value=root / "flow-server.log"))
		cls.enterClassContext(patch.object(lifecycle, "_redis_url", return_value=None))
		# the real lock file lives in the bench's config folder
		cls.enterClassContext(patch.object(lifecycle, "filelock"))
		cls.enterClassContext(patch.dict(frappe.local.conf, {"flow_server_secret": TOKEN}))
		site.mkdir(parents=True)
		(site / "site_config.json").write_text(json.dumps({"flow_server_secret": TOKEN}))
		lifecycle.start()
		cls.addClassCleanup(lifecycle.stop)

	def setUp(self):
		sync_builtin_tools()
		self.client = DaemonClient.for_site()
		self.addCleanup(self.client.close)
		self.model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Live Session Model",
				"model_id": "openai/gpt-4o-mini",
				"api_key": "sk-live",
				"enabled": 1,
			}
		).insert()
		self.agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Live Session Agent",
				"model": self.model.name,
				"instructions": "Reply briefly.",
				"tools": [{"tool": "read_records"}, {"tool": "execute"}],
				"enabled": 1,
			}
		).insert()
		original = FlowSession.server_config
		# the server's keyless mock model answers every message with an echo
		self.enterContext(
			patch.object(
				FlowSession, "server_config", lambda doc, **kw: {**original(doc, **kw), "model": "mock"}
			)
		)
		self.enterContext(patch("frappe.flow.lib.model.resolve_provider_credentials", return_value={}))

	def tearDown(self):
		frappe.db.rollback()

	def wait_idle(self, session_name: str) -> None:
		for _ in range(100):
			if not self.client.get_session(session_name)["running"]:
				return
			time.sleep(0.01)
		self.fail("daemon run did not finish")

	def settle(self, session, run):
		self.wait_idle(session.name)
		session.sync()
		session.reload()
		run.reload()
