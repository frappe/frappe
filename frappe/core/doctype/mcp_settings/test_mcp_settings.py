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
		original = {
			field: doc.get(field)
			for field in ("enable_mcp", "server_name", "server_description", "agent_instructions")
		}
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

	def site_info(self):
		return self.request(
			{
				"jsonrpc": "2.0",
				"id": 1,
				"method": "tools/call",
				"params": {"name": "get_site_info", "arguments": {}},
			}
		)

	def test_field_order_and_enabled_default(self):
		meta = frappe.get_meta("MCP Settings")
		self.assertEqual(
			[field.fieldname for field in meta.fields],
			["enable_mcp", "server_name", "server_description", "agent_instructions"],
		)
		self.assertEqual(frappe.new_doc("MCP Settings").enable_mcp, 1)

	def test_empty_instructions_send_only_default_instructions(self):
		from frappe.mcp.server import server_configuration

		with self.settings(agent_instructions="  "):
			self.assertEqual(server_configuration()["instructions"], protocol.DEFAULT_INSTRUCTIONS)

	def test_empty_settings_use_site_identity(self):
		with self.settings(server_name="", server_description="", enable_mcp=1, agent_instructions=""):
			result = self.site_info().json["result"]["structuredContent"]
		self.assertEqual(result["server_info"], {"name": self.site, "version": frappe.__version__})
		self.assertEqual(result["site"], self.site)
		self.assertEqual(result["user"], self.user)

	def test_server_information_uses_site_settings(self):
		with self.settings(
			server_name="Example Accounting",
			server_description="Invoices for Example India",
			enable_mcp=1,
			agent_instructions="Search for existing customers before creating one.",
		):
			result = self.site_info().json["result"]["structuredContent"]
			response = self.request(
				{
					"jsonrpc": "2.0",
					"id": 1,
					"method": "initialize",
					"params": {
						"protocolVersion": protocol.LEGACY_VERSION,
						"capabilities": {},
						"clientInfo": {"name": "test", "version": "1"},
					},
				}
			)
			modern = self.request(
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
			)
		self.assertEqual(result["server_info"]["name"], "Example Accounting")
		self.assertEqual(result["server_info"]["description"], "Invoices for Example India")
		self.assertEqual(result["site"], self.site)
		self.assertEqual(response.json["result"]["serverInfo"], result["server_info"])
		self.assertEqual(modern.json["result"]["serverInfo"], result["server_info"])
		self.assertEqual(response.json["result"]["instructions"], result["instructions"])
		self.assertEqual(modern.json["result"]["instructions"], result["instructions"])
		self.assertTrue(result["instructions"].startswith(protocol.DEFAULT_INSTRUCTIONS))
		self.assertTrue(
			result["instructions"].endswith("\nSearch for existing customers before creating one.")
		)

	def test_settings_changes_invalidate_cached_server_information(self):
		with self.settings(server_name="First Site", enable_mcp=1):
			self.assertEqual(
				self.site_info().json["result"]["structuredContent"]["server_info"]["name"], "First Site"
			)
			with self.settings(server_name="Second Site"):
				self.assertEqual(
					self.site_info().json["result"]["structuredContent"]["server_info"]["name"], "Second Site"
				)

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
