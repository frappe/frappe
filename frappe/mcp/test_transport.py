# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.mcp import protocol
from frappe.mcp.test_utils import McpTestCase


class TestMcpTransport(McpTestCase):
	def test_authenticated_ping(self):
		for path in ("/api/v2/mcp", "/api/v2/mcp/"):
			self.assertEqual(self.ping(path=path).json, {"jsonrpc": "2.0", "id": 1, "result": {}})

	def test_mcp_is_only_available_under_v2(self):
		for path in ("/api/mcp", "/api/v1/mcp"):
			with self.subTest(path=path):
				self.assertEqual(self.ping(path=path).status_code, 404)

	def test_http_checks(self):
		self.assertEqual(self.ping(auth=False).status_code, 401)
		for method in ("GET", "DELETE"):
			response = self.ping(method=method)
			self.assertEqual(response.status_code, 405)
			self.assertEqual(response.headers["Allow"], "POST")
		self.assertEqual(self.ping(headers={"Content-Type": "text/plain"}).status_code, 415)
		self.assertEqual(self.ping(headers={"Accept": "text/event-stream"}).status_code, 406)

	def test_invalid_envelopes(self):
		for payload in ([], {}, {"jsonrpc": "2.0", "method": "ping", "id": True}):
			with self.subTest(payload=payload):
				self.assertEqual(self.request(payload).json["error"]["code"], protocol.INVALID_REQUEST)

	def test_legacy_initialize(self):
		response = self.request(
			{
				"jsonrpc": "2.0",
				"id": "init",
				"method": "initialize",
				"params": {
					"protocolVersion": protocol.LATEST_VERSION,
					"capabilities": {},
					"clientInfo": {"name": "test", "version": "1"},
				},
			}
		)
		self.assertEqual(response.json["result"]["protocolVersion"], protocol.LEGACY_VERSION)
		self.assertEqual(self.request({"jsonrpc": "2.0", "id": 1, "method": "initialize"}).status_code, 400)

	def test_modern_discovery(self):
		payload = {
			"jsonrpc": "2.0",
			"id": 1,
			"method": "server/discover",
			"params": {
				"_meta": {protocol.META_VERSION: protocol.LATEST_VERSION, protocol.META_CAPABILITIES: {}}
			},
		}
		headers = {"MCP-Protocol-Version": protocol.LATEST_VERSION, "Mcp-Method": "server/discover"}
		response = self.request(payload, headers=headers)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["result"]["supportedVersions"], list(protocol.SUPPORTED_VERSIONS))
		self.assertEqual(response.json["result"]["resultType"], "complete")
		headers["Mcp-Method"] = "ping"
		self.assertEqual(
			self.request(payload, headers=headers).json["error"]["code"], protocol.HEADER_MISMATCH
		)
		self.assertEqual(self.request(payload).json["error"]["code"], protocol.HEADER_MISMATCH)

	def test_unsupported_version(self):
		self.assertEqual(
			self.ping(headers={"MCP-Protocol-Version": "unknown"}).json["error"]["code"],
			protocol.UNSUPPORTED_VERSION,
		)

	def test_notification(self):
		response = self.request({"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "missing"}})
		self.assertEqual(response.status_code, 202)
		self.assertEqual(response.data, b"")

	def test_dispatch(self):
		self.assertEqual(
			self.request({"jsonrpc": "2.0", "id": 1, "method": "missing"}).json["error"]["code"],
			protocol.METHOD_NOT_FOUND,
		)
		response = self.request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
		self.assertEqual(
			[tool["name"] for tool in response.json["result"]["tools"]],
			[
				"search_doctypes",
				"get_doctype_schema",
				"search_methods",
				"get_method_schema",
				"list_document_methods",
				"list_documents",
				"get_document",
				"count_documents",
				"create_document",
				"update_document",
				"delete_document",
				"call_method",
				"call_document_method",
			],
		)

	def test_unexpected_error_uses_json_rpc_envelope(self):
		with patch("frappe.mcp.server.server_configuration", side_effect=ZeroDivisionError("secret")):
			response = self.request(
				{
					"jsonrpc": "2.0",
					"id": 7,
					"method": "initialize",
					"params": {
						"protocolVersion": protocol.LEGACY_VERSION,
						"capabilities": {},
						"clientInfo": {"name": "test", "version": "1"},
					},
				}
			)
		self.assertEqual(response.status_code, 500)
		self.assertEqual(
			response.json,
			{
				"jsonrpc": "2.0",
				"id": 7,
				"error": {"code": protocol.INTERNAL_ERROR, "message": "Internal error"},
			},
		)

	def test_origin(self):
		self.assertEqual(self.ping(headers={"Origin": "https://untrusted.example.com"}).status_code, 403)
		self.assertEqual(self.ping(headers={"Origin": "http://localhost"}).status_code, 200)
