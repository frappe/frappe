# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.mcp import protocol
from frappe.mcp.test_utils import McpTestCase


class TestMCPSettings(McpTestCase):
	@contextmanager
	def settings(self, **values):
		doc = frappe.get_doc("MCP Settings")
		original = {field: doc.get(field) for field in ("enable_mcp", "server_name", "agent_instructions")}
		try:
			doc.update(values)
			doc.save()
			frappe.db.commit()  # nosemgrep
			yield
		finally:
			frappe.set_user("Administrator")
			doc = frappe.get_doc("MCP Settings")
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

	def test_field_order_and_enabled_default(self):
		meta = frappe.get_meta("MCP Settings")
		self.assertEqual(
			[field.fieldname for field in meta.fields],
			["enable_mcp", "server_name", "agent_instructions"],
		)
		self.assertEqual(frappe.new_doc("MCP Settings").enable_mcp, 1)

	def test_instructions_describe_site_user_and_apps(self):
		with self.settings(agent_instructions="  "):
			instructions = self.initialize(headers={"Host": "erp.example.com"})["instructions"]
		self.assertIn("site at erp.example.com", instructions)
		self.assertIn(self.user, instructions)
		self.assertIn(
			"- Frappe Framework (frappe): " + frappe.get_hooks("app_description", app_name="frappe")[0],
			instructions,
		)
		self.assertFalse(instructions.endswith("\n"))

	def test_empty_server_name_uses_scrubbed_host_name(self):
		with self.settings(server_name="", enable_mcp=1):
			result = self.initialize(headers={"Host": "ERP-1.example.com:8443"})
		self.assertEqual(result["serverInfo"]["name"], "erp_1_example_com_8443")
		self.assertEqual(result["serverInfo"]["version"], frappe.__version__)

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
		self.assertTrue(
			legacy["instructions"].endswith("\n\nSearch for existing customers before creating one.")
		)

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

	def test_site_config_still_forces_endpoint_off(self):
		from werkzeug.exceptions import NotFound

		from frappe.mcp import handle

		with self.settings(enable_mcp=1), patch.dict(frappe.conf, {"disable_mcp_server": True}):
			self.assertRaises(NotFound, handle)

	def test_normal_user_cannot_change_settings(self):
		doc = frappe.get_doc("MCP Settings")
		with self.set_user(self.user):
			doc.server_name = "Unauthorized name"
			with self.assertRaises(frappe.PermissionError):
				doc.save()
