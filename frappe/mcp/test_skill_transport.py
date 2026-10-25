# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import base64
from unittest.mock import patch

import frappe
from frappe.mcp import protocol
from frappe.mcp.skills import EXTENSION
from frappe.mcp.test_skills import SkillFixtures
from frappe.mcp.test_utils import McpTestCase


class TestSkillTransport(SkillFixtures, McpTestCase):
	def setUp(self):
		super().setUp()
		self.setup_skills()
		self.enterContext(self.change_settings("System Settings", enable_mcp=1, commit=True))
		get_path = frappe.get_app_source_path
		self.app_source_path = get_path
		self.enterContext(
			patch(
				"frappe.get_app_source_path",
				side_effect=lambda app, *parts: (
					str(self.root / app / "skills") if parts == ("skills",) else get_path(app, *parts)
				),
			)
		)

	def rpc(self, method, params=None, *, modern=True, auth=True):
		params = dict(params or {})
		headers = {}
		if modern:
			params["_meta"] = {
				protocol.META_VERSION: protocol.LATEST_VERSION,
				protocol.META_CAPABILITIES: {"extensions": {EXTENSION: {}}},
				protocol.META_CLIENT: {"name": "test", "version": "1"},
			}
			headers = {"MCP-Protocol-Version": protocol.LATEST_VERSION, "Mcp-Method": method}
			if method == "resources/read" and "uri" in params:
				headers["Mcp-Name"] = params["uri"]
		return self.request(
			{"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, headers=headers, auth=auth
		)

	def test_discovery_advertises_resources_and_skills(self):
		modern = self.rpc("server/discover").json["result"]
		legacy = self.rpc(
			"initialize",
			{
				"protocolVersion": protocol.LEGACY_VERSION,
				"capabilities": {},
				"clientInfo": {"name": "test", "version": "1"},
			},
			modern=False,
		).json["result"]
		for result in (modern, legacy):
			self.assertIn("resources", result["capabilities"])
			self.assertEqual(result["capabilities"]["extensions"][EXTENSION], {})

	def test_normal_desk_user_can_discover_and_read_nested_skills(self):
		for modern in (True, False):
			with self.subTest(modern=modern):
				listing = self.rpc("skills/list", modern=modern).json["result"]
				self.assertEqual(len(listing["skills"]), 2)
				uri = "skill://frappe/billing/refunds/review/SKILL.md"
				entry = next(entry for entry in listing["skills"] if entry["uri"] == uri)
				self.assertEqual(
					self.rpc("skills/get", {"uri": uri}, modern=modern).json["result"]["skill"], entry
				)
				content = self.rpc("resources/read", {"uri": uri}, modern=modern).json["result"]
				self.assertIn("name: review", content["contents"][0]["text"])
				if modern:
					self.assertEqual(listing["resultType"], "complete")
					self.assertEqual(listing["cacheScope"], "private")
					self.assertEqual(content["ttlMs"], 0)
				else:
					self.assertNotIn("ttlMs", listing)

	def test_base_resources(self):
		listing = self.rpc("resources/list").json["result"]["resources"]
		self.assertEqual(len(listing), 2)
		self.assertTrue(all(resource["mimeType"] == "text/markdown" for resource in listing))
		self.assertEqual(self.rpc("resources/templates/list").json["result"]["resourceTemplates"], [])

	def test_invalid_params_use_protocol_errors(self):
		for method, params in (
			("skills/get", {}),
			("skills/get", {"uri": "skill://frappe/billing/refunds"}),
			("skills/get", {"uri": "skill://frappe/missing/SKILL.md"}),
			("resources/read", {"uri": "skill://frappe/private.txt"}),
			("skills/list", {"cursor": 42}),
		):
			with self.subTest(method=method, params=params):
				response = self.rpc(method, params)
				self.assertEqual(response.status_code, 400)
				self.assertEqual(response.json["error"]["code"], protocol.INVALID_PARAMS)

	def test_skill_reads_require_authentication(self):
		for method in ("skills/list", "resources/read"):
			with self.subTest(method=method):
				self.assertEqual(self.rpc(method, auth=False).status_code, 401)

	def test_installed_app_skill_is_readable_without_database_sync(self):
		with patch("frappe.get_app_source_path", side_effect=self.app_source_path):
			uri = "skill://frappe/studio-app-building/SKILL.md"
			response = self.rpc("skills/get", {"uri": uri})
			self.assertEqual(response.status_code, 200)
			entry = response.json["result"]["skill"]
			self.assertEqual(entry["frontmatter"]["name"], "studio-app-building")
			self.assertIn(
				"skill://frappe/studio-app-building/RULES.md",
				{resource["uri"] for resource in entry["resources"]},
			)
			self.assertEqual(self.rpc("resources/read", {"uri": uri}).status_code, 200)

	def test_resource_uri_header_must_match_body(self):
		uri = "skill://frappe/billing/refunds/SKILL.md"
		payload = {
			"jsonrpc": "2.0",
			"id": 1,
			"method": "resources/read",
			"params": {
				"uri": uri,
				"_meta": {
					protocol.META_VERSION: protocol.LATEST_VERSION,
					protocol.META_CAPABILITIES: {},
					protocol.META_CLIENT: {"name": "test", "version": "1"},
				},
			},
		}
		headers = {"MCP-Protocol-Version": protocol.LATEST_VERSION, "Mcp-Method": "resources/read"}
		for name in (None, "skill://frappe/other/SKILL.md", "=?base64?invalid?="):
			if name is not None:
				headers["Mcp-Name"] = name
			with self.subTest(name=name):
				response = self.request(payload, headers=headers)
				self.assertEqual(response.status_code, 400)
				self.assertEqual(response.json["error"]["code"], protocol.HEADER_MISMATCH)
		headers["Mcp-Name"] = "=?base64?" + base64.b64encode(uri.encode()).decode() + "?="
		self.assertEqual(self.request(payload, headers=headers).status_code, 200)
