# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.mcp import protocol
from frappe.mcp.test_utils import McpTestCase


class TestSettings(McpTestCase):
	@contextmanager
	def settings(self, **values):
		doc = frappe.get_doc("System Settings")
		original = {field: doc.get(field) for field in ("enable_mcp", "server_name", "agent_instructions")}
		try:
			doc.update(values)
			doc.save()
			frappe.db.commit()  # nosemgrep
			yield
		finally:
			frappe.set_user("Administrator")
			doc = frappe.get_doc("System Settings")
			doc.update(original)
			doc.save()
			frappe.db.commit()  # nosemgrep

	def initialize(self, headers=None):
		return self.request(
			{
				"jsonrpc": "2.0",
				"id": 1,
				"method": "initialize",
				"params": {
					"protocolVersion": protocol.LEGACY_VERSION,
					"capabilities": {},
					"clientInfo": {"name": "test", "version": "1"},
				},
			},
			headers=headers,
		).json["result"]

	def discover(self):
		return self.request(
			{
				"jsonrpc": "2.0",
				"id": 1,
				"method": "server/discover",
				"params": {
					"_meta": {
						protocol.META_VERSION: protocol.LATEST_VERSION,
						protocol.META_CAPABILITIES: {},
					}
				},
			},
			headers={"MCP-Protocol-Version": protocol.LATEST_VERSION, "Mcp-Method": "server/discover"},
		).json["result"]

	def test_server_information_uses_site_settings(self):
		with self.settings(
			server_name="Example Accounting",
			enable_mcp=1,
			agent_instructions="Search for existing customers before creating one.",
		):
			legacy = self.initialize()
			modern = self.discover()
		server_info = {"name": "Example Accounting", "version": frappe.__version__}
		self.assertEqual(legacy["serverInfo"], server_info)
		self.assertEqual(modern["serverInfo"], server_info)
		self.assertEqual(modern["instructions"], legacy["instructions"])
		self.assertIn("Search for existing customers before creating one.", legacy["instructions"])

	def test_settings_changes_invalidate_cached_server_information(self):
		with self.settings(server_name="First Site", enable_mcp=1):
			self.assertEqual(self.initialize()["serverInfo"]["name"], "First Site")
			with self.settings(server_name="Second Site"):
				self.assertEqual(self.initialize()["serverInfo"]["name"], "Second Site")

	def test_unchecking_checkbox_disables_endpoint_and_checking_enables_it(self):
		with self.settings(enable_mcp=0):
			self.assertEqual(self.ping().status_code, 404)
		with self.settings(enable_mcp=1):
			self.assertEqual(self.ping().status_code, 200)

	def test_enable_setting_controls_endpoint_even_with_legacy_site_config(self):
		with self.settings(enable_mcp=1), patch.dict(frappe.conf, {"disable_mcp_server": True}):
			self.assertEqual(self.ping().status_code, 200)

	def test_normal_user_cannot_change_settings(self):
		doc = frappe.get_doc("System Settings")
		with self.set_user(self.user):
			doc.server_name = "Unauthorized name"
			with self.assertRaises(frappe.PermissionError):
				doc.save()
