# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import base64
import errno
from unittest.mock import patch

import frappe
from frappe.mcp import protocol
from frappe.mcp.skills import SKILLS_EXTENSION
from frappe.mcp.test_skills import SkillFixtures
from frappe.mcp.test_utils import McpTestCase


class TestSkillTransport(SkillFixtures, McpTestCase):
	def setUp(self):
		super().setUp()
		self.setup_skills()
		self.enterContext(self.change_settings("System Settings", enable_mcp=1, commit=True))
		get_path = frappe.get_app_source_path
		self.enterContext(
			patch(
				"frappe.get_app_source_path",
				side_effect=lambda app, *parts: (
					str(self.root / app / "skills") if parts == ("skills",) else get_path(app, *parts)
				),
			)
		)

	def rpc(self, method, params=None, *, modern=True, auth=True, headers=None):
		params = dict(params or {})
		request_headers = {}
		if modern:
			params["_meta"] = {
				protocol.META_VERSION: protocol.LATEST_VERSION,
				protocol.META_CAPABILITIES: {"extensions": {SKILLS_EXTENSION: {}}},
				protocol.META_CLIENT: {"name": "test", "version": "1"},
			}
			request_headers = {"MCP-Protocol-Version": protocol.LATEST_VERSION, "Mcp-Method": method}
			if method == "resources/read" and "uri" in params:
				request_headers.update({"Mcp-Name": params["uri"]} if headers is None else headers)
		return self.request(
			{"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
			headers=request_headers,
			auth=auth,
		)

	def test_normal_desk_user_can_discover_and_read_skills_in_both_protocol_versions(self):
		for modern in (True, False):
			with self.subTest(modern=modern):
				discovery = self.rpc(
					"server/discover" if modern else "initialize",
					{
						"protocolVersion": protocol.LEGACY_VERSION,
						"capabilities": {},
						"clientInfo": {"name": "test", "version": "1"},
					},
					modern=modern,
				).json["result"]
				self.assertIn("resources", discovery["capabilities"])
				self.assertEqual(discovery["capabilities"]["tools"], {"listChanged": False})
				self.assertEqual(
					discovery["capabilities"]["extensions"][SKILLS_EXTENSION], {"directoryRead": True}
				)
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

	def test_resource_routes(self):
		listing = self.rpc("resources/list").json["result"]["resources"]
		self.assertEqual(len(listing), 2)
		self.assertTrue(all(resource["mimeType"] == "text/markdown" for resource in listing))
		self.assertEqual(self.rpc("resources/templates/list").json["result"]["resourceTemplates"], [])
		directory = self.rpc("resources/directory/read", {"uri": "skill://frappe/billing/refunds/review"})
		self.assertEqual(directory.status_code, 200)
		self.assertEqual(
			directory.json["result"]["resources"][0]["uri"], "skill://frappe/billing/refunds/review/SKILL.md"
		)

	def test_failures_use_protocol_errors(self):
		for method, params in (
			("skills/get", {}),
			("skills/get", {"uri": "skill://frappe/billing/refunds"}),
			("skills/get", {"uri": "skill://frappe/missing/SKILL.md"}),
			("resources/read", {"uri": "skill://frappe/private.txt"}),
			("resources/read", {"uri": "skill://frappe/billing/refunds/.env"}),
			("resources/directory/read", {"uri": "skill://frappe/billing/refunds/SKILL.md"}),
			("skills/list", {"cursor": 42}),
		):
			with self.subTest(method=method, params=params):
				response = self.rpc(method, params)
				self.assertEqual(response.status_code, 400)
				self.assertEqual(response.json["error"]["code"], protocol.INVALID_PARAMS)
		for method, uri in (
			("resources/read", "skill://frappe/billing/refunds/SKILL.md"),
			("resources/directory/read", "skill://frappe/billing/refunds"),
		):
			with (
				self.subTest(method=method),
				patch("frappe.mcp.skill_files.os.open", side_effect=OSError(errno.EIO, "disk failure")),
			):
				response = self.rpc(method, {"uri": uri})
			self.assertEqual(response.status_code, 500)
			self.assertEqual(
				response.json["error"], {"code": protocol.INTERNAL_ERROR, "message": "Internal error"}
			)

	def test_skill_reads_require_authentication(self):
		for method in (
			"skills/list",
			"skills/get",
			"resources/list",
			"resources/read",
			"resources/directory/read",
		):
			with self.subTest(method=method):
				self.assertEqual(self.rpc(method, auth=False).status_code, 401)

	def test_resource_uri_header_must_match_body(self):
		uri = "skill://frappe/billing/refunds/SKILL.md"
		for name in (None, "skill://frappe/other/SKILL.md", "=?base64?invalid?="):
			with self.subTest(name=name):
				response = self.rpc(
					"resources/read", {"uri": uri}, headers={"Mcp-Name": name} if name else {}
				)
				self.assertEqual(response.status_code, 400)
				self.assertEqual(response.json["error"]["code"], protocol.HEADER_MISMATCH)
		encoded = "=?base64?" + base64.b64encode(uri.encode()).decode() + "?="
		self.assertEqual(
			self.rpc("resources/read", {"uri": uri}, headers={"Mcp-Name": encoded}).status_code, 200
		)
