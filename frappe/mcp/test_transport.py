# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
from unittest.mock import patch

import frappe
from frappe.core.doctype.user.user import generate_keys
from frappe.mcp import protocol
from frappe.tests import IntegrationTestCase
from frappe.tests.test_api import make_request
from frappe.utils import get_test_client


class TestMcpTransport(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.user = "mcp.transport@example.com"
		if not frappe.db.exists("User", self.user):
			frappe.get_doc(
				doctype="User", email=self.user, first_name="MCP Transport", send_welcome_email=0
			).insert()
		keys = generate_keys(self.user)
		self.authorization = f"token {keys['api_key']}:{keys['api_secret']}"
		self.site = frappe.local.site

	def request(self, payload=None, *, method="POST", headers=None, body=None, path="/api/mcp", auth=True):
		request_headers = {"Content-Type": "application/json", "Accept": "application/json"}
		if auth:
			request_headers["Authorization"] = self.authorization
		request_headers.update(headers or {})
		return make_request(
			get_test_client(use_cookies=False).open,
			args=(),
			kwargs={
				"path": path,
				"method": method,
				"headers": request_headers,
				"data": body if body is not None else json.dumps(payload),
			},
			site=self.site,
		)

	def ping(self, **kwargs):
		return self.request({"jsonrpc": "2.0", "id": 1, "method": "ping"}, **kwargs)

	def test_authenticated_ping(self):
		for path in ("/api/mcp", "/api/mcp/"):
			self.assertEqual(self.ping(path=path).json, {"jsonrpc": "2.0", "id": 1, "result": {}})

	def test_http_checks(self):
		self.assertEqual(self.ping(auth=False).status_code, 401)
		for method in ("GET", "DELETE"):
			response = self.ping(method=method)
			self.assertEqual(response.status_code, 405)
			self.assertEqual(response.headers["Allow"], "POST")
		self.assertEqual(self.ping(headers={"Content-Type": "text/plain"}).status_code, 415)
		self.assertEqual(self.ping(headers={"Accept": "text/event-stream"}).status_code, 406)

	def test_parse_errors(self):
		for body in ('{"jsonrpc":', '{"value": NaN}', '{"value": Infinity}'):
			with self.subTest(body=body):
				response = self.request(body=body)
				self.assertEqual(response.status_code, 400)
				self.assertEqual(response.json["error"]["code"], protocol.PARSE_ERROR)

	def test_invalid_envelopes(self):
		for payload in ([], None, {}, {"jsonrpc": "2.0", "method": "ping", "id": True}):
			with self.subTest(payload=payload):
				self.assertEqual(self.request(payload).json["error"]["code"], protocol.INVALID_REQUEST)

	def test_command_cannot_override_routing(self):
		response = self.request(
			{"jsonrpc": "2.0", "id": 1, "method": "ping", "cmd": "frappe.auth.get_logged_user"}
		)
		self.assertEqual(response.json["result"], {})
		self.assertNotIn("message", response.json)

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
		self.assertEqual(
			self.request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).json["result"], {"tools": []}
		)

	def test_origin(self):
		self.assertEqual(self.ping(headers={"Origin": "https://untrusted.example.com"}).status_code, 403)
		self.assertEqual(self.ping(headers={"Origin": "http://localhost"}).status_code, 200)

	def test_disabled_endpoint(self):
		from werkzeug.exceptions import NotFound

		from frappe.mcp import handle

		with patch.dict(frappe.conf, {"disable_mcp_server": True}):
			self.assertRaises(NotFound, handle)

	def test_regular_api(self):
		response = self.request({}, path="/api/method/frappe.auth.get_logged_user")
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["message"], self.user)
