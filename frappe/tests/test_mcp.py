"""Exercise the SDK transport through Frappe WSGI as a normal user."""

from unittest.mock import patch
from urllib.parse import urlsplit

import frappe
from frappe.tests.test_api import FrappeAPITestCase, make_request
from frappe.tests.utils import whitelist_for_tests


@whitelist_for_tests(methods=["GET"])
def read_identity():
	return {"user": frappe.session.user, "site": frappe.local.site, "verb": frappe.request.method}


@whitelist_for_tests(methods=["POST"])
def write_then_fail(description: str):
	frappe.get_doc(doctype="ToDo", description=description).insert()
	frappe.throw("Deliberate failure")


class TestMCP(FrappeAPITestCase):
	USER = "mcp-demo@example.com"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		dev_server = patch("frappe._dev_server", True)
		dev_server.start()
		cls.addClassCleanup(dev_server.stop)
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": cls.USER,
				"first_name": "MCP Demo",
				"user_type": "System User",
				"send_welcome_email": 0,
				"api_key": frappe.generate_hash(length=15),
				"api_secret": frappe.generate_hash(length=15),
			}
		).insert()
		cls.token = f"token {user.api_key}:{user.get_password('api_secret')}"
		frappe.db.commit()
		cls.addClassCleanup(cls.cleanup_user)

	@classmethod
	def cleanup_user(cls):
		frappe.set_user("Administrator")
		for name in frappe.get_all("ToDo", filters={"owner": cls.USER}, pluck="name"):
			frappe.delete_doc("ToDo", name)
		frappe.delete_doc("User", cls.USER)
		frappe.db.commit()

	def rpc(self, method, params=None, modern=False, authenticated=True, **kwargs):
		headers = {"Accept": "application/json, text/event-stream", "Host": urlsplit(self.site_url).netloc}
		if authenticated:
			headers["Authorization"] = self.token
		if modern:
			headers.update({"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": method})
			params = {
				**(params or {}),
				"_meta": {
					"io.modelcontextprotocol/protocolVersion": "2026-07-28",
					"io.modelcontextprotocol/clientCapabilities": {},
				},
			}
			if method == "tools/call":
				headers["Mcp-Name"] = params["name"]
		return self.post(
			"/api/mcp",
			{"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
			headers=headers,
			**kwargs,
		)

	def tool(self, name, arguments, modern=False):
		response = self.rpc("tools/call", {"name": name, "arguments": arguments}, modern=modern)
		self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
		return response.json["result"]

	def test_protocol_and_tool_schemas(self):
		response = self.rpc(
			"initialize",
			{
				"protocolVersion": "2025-11-25",
				"capabilities": {},
				"clientInfo": {"name": "test", "version": "1"},
			},
		)
		self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
		self.assertEqual(response.json["result"]["protocolVersion"], "2025-11-25")
		for modern in (False, True):
			response = self.rpc("tools/list", modern=modern)
			self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
			tools = response.json["result"]["tools"]
			self.assertEqual(
				{tool["name"] for tool in tools},
				{"discover", "get_documents", "write_documents", "call_method"},
			)
			read = next(tool for tool in tools if tool["name"] == "get_documents")
			self.assertEqual(read["inputSchema"]["properties"]["limit"]["maximum"], 100)
			self.assertTrue(read["annotations"]["readOnlyHint"])

	def test_modern_discovery(self):
		response = self.rpc("server/discover", modern=True)
		self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
		self.assertIn("2026-07-28", response.json["result"]["supportedVersions"])

	def test_document_round_trip(self):
		for modern in (False, True):
			created = self.tool(
				"write_documents",
				{"action": "create", "doctype": "ToDo", "data": {"description": "MCP test"}},
				modern,
			)
			self.assertFalse(created["isError"], created)
			name = created["structuredContent"]["document"]["name"]
			read = self.tool("get_documents", {"doctype": "ToDo", "name": name}, modern)
			self.assertEqual(read["structuredContent"]["document"]["owner"], self.USER)
			updated = self.tool(
				"write_documents",
				{"action": "update", "doctype": "ToDo", "name": name, "data": {"description": "Updated"}},
				modern,
			)
			self.assertEqual(updated["structuredContent"]["document"]["description"], "Updated")
			comment = self.tool(
				"call_method",
				{"doctype": "ToDo", "name": name, "method": "add_comment", "args": {"text": "MCP comment"}},
				modern,
			)
			self.assertFalse(comment["isError"], comment)
			self.assertEqual(comment["structuredContent"]["result"]["owner"], self.USER)
			count = self.tool(
				"get_documents", {"doctype": "ToDo", "filters": {"name": name}, "count_only": True}, modern
			)
			self.assertEqual(count["structuredContent"]["count"], 1)
			deleted = self.tool(
				"write_documents", {"action": "delete", "doctype": "ToDo", "name": name}, modern
			)
			self.assertFalse(deleted["isError"], deleted)
			self.assertFalse(frappe.db.exists("ToDo", name))

	def test_discover_and_permission_denial(self):
		allowed = self.tool("discover", {"doctype": "ToDo"})
		self.assertFalse(allowed["isError"], allowed)
		self.assertTrue(allowed["structuredContent"]["fields"])
		denied = self.tool("get_documents", {"doctype": "User", "name": "Administrator"})
		self.assertTrue(denied["isError"])
		denied = self.tool(
			"write_documents", {"action": "create", "doctype": "Role", "data": {"role_name": "MCP denied"}}
		)
		self.assertTrue(denied["isError"])
		self.assertFalse(frappe.db.exists("Role", "MCP denied"))

	def test_method_identity_and_rollback(self):
		identity = self.tool("call_method", {"method": f"{__name__}.read_identity"}, modern=True)
		self.assertFalse(identity["isError"], identity)
		self.assertEqual(
			identity["structuredContent"]["result"],
			{"user": self.USER, "site": frappe.local.site, "verb": "GET"},
		)
		description = frappe.generate_hash()
		failed = self.tool(
			"call_method", {"method": f"{__name__}.write_then_fail", "args": {"description": description}}
		)
		self.assertTrue(failed["isError"])
		self.assertFalse(frappe.db.exists("ToDo", {"description": description}))
		wrong_verb = self.tool("call_method", {"method": f"{__name__}.read_identity", "http_method": "POST"})
		self.assertTrue(wrong_verb["isError"])
		private = self.tool("call_method", {"method": "frappe.get_roles"})
		self.assertTrue(private["isError"])

	def test_input_validation(self):
		for arguments in ({"doctype": "ToDo", "limit": 101}, {"doctype": "ToDo", "start": -1}):
			response = self.tool("get_documents", arguments)
			self.assertTrue(response["isError"])
		response = self.tool(
			"write_documents",
			{"action": "create", "doctype": "Role", "data": {"flags": {"ignore_permissions": True}}},
		)
		self.assertTrue(response["isError"])

	def test_list_and_site_discovery(self):
		for modern in (False, True):
			response = self.tool("discover", {}, modern)
			self.assertFalse(response["isError"], response)
			self.assertEqual(response["structuredContent"]["user"], self.USER)
			response = self.tool("get_documents", {"doctype": "ToDo", "limit": 1}, modern)
			self.assertFalse(response["isError"], response)
			self.assertLessEqual(len(response["structuredContent"]["documents"]), 1)

	def test_rest_request_body_is_unchanged(self):
		response = self.post(
			"/api/v2/method/frappe.auth.get_logged_user", {}, headers={"Authorization": self.token}
		)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["data"], self.USER)
		response = self.get("/api/v2/document/ToDo", {"limit": 1}, headers={"Authorization": self.token})
		self.assertEqual(response.status_code, 200)
		self.assertLessEqual(len(response.json["data"]), 1)

	def test_sdk_client_over_http(self):
		from threading import Thread

		import anyio
		import httpx2
		from mcp import Client
		from mcp.client.streamable_http import streamable_http_client
		from werkzeug.serving import make_server

		from frappe.app import application

		async def check_clients(url):
			async with httpx2.AsyncClient(
				headers={"Authorization": self.token, "Host": urlsplit(self.site_url).netloc}
			) as http:
				for mode in ("auto", "legacy"):
					async with Client(streamable_http_client(url, http_client=http), mode=mode) as client:
						tools = await client.list_tools()
						self.assertEqual(len(tools.tools), 4)
						response = await client.call_tool("discover", {"doctype": "ToDo"})
						self.assertFalse(response.is_error)
						self.assertEqual(response.structured_content["doctype"], "ToDo")

		frappe.db.commit()
		with patch("frappe.app.get_site_name", return_value=frappe.local.site):
			server = make_server("127.0.0.1", 0, application)
			thread = Thread(target=server.serve_forever, daemon=True)
			thread.start()
			try:
				anyio.run(check_clients, f"http://127.0.0.1:{server.server_port}/api/mcp")
			finally:
				server.shutdown()
				thread.join()
				server.server_close()

	def test_transport_notifications_and_header_checks(self):
		headers = {
			"Authorization": self.token,
			"Host": urlsplit(self.site_url).netloc,
			"Accept": "application/json, text/event-stream",
		}
		response = self.post(
			"/api/mcp", {"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=headers
		)
		self.assertEqual(response.status_code, 202)
		self.assertFalse(response.data)
		for verb in (self.TEST_CLIENT.get, self.TEST_CLIENT.delete):
			response = make_request(target=verb, args=("/api/mcp",), kwargs={"headers": headers})
			self.assertEqual(response.status_code, 405)
		response = self.post(
			"/api/mcp",
			{
				"jsonrpc": "2.0",
				"id": 1,
				"method": "tools/list",
				"params": {
					"_meta": {
						"io.modelcontextprotocol/protocolVersion": "2026-07-28",
						"io.modelcontextprotocol/clientCapabilities": {},
					}
				},
			},
			headers={**headers, "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/call"},
		)
		self.assertIn("error", response.json)

	def test_guest_disabled_origin_and_invalid_json(self):
		self.assertEqual(self.rpc("tools/list", authenticated=False).status_code, 401)
		with patch.dict(frappe.conf, {"disable_mcp_server": True}):
			# WSGI loads config in another thread, so test the handler with its own context.
			from werkzeug.exceptions import NotFound

			from frappe.mcp import handle

			self.assertRaises(NotFound, handle)
		response = self.post(
			"/api/mcp",
			{},
			headers={
				"Authorization": self.token,
				"Origin": "https://untrusted.example.com",
				"Host": urlsplit(self.site_url).netloc,
			},
		)
		self.assertEqual(response.status_code, 403)
		response = make_request(
			target=self.TEST_CLIENT.post,
			args=("/api/mcp",),
			kwargs={
				"data": "{broken",
				"content_type": "application/json",
				"headers": {
					"Authorization": self.token,
					"Accept": "application/json, text/event-stream",
					"Host": urlsplit(self.site_url).netloc,
				},
			},
		)
		self.assertEqual(response.status_code, 400)
		self.assertIn("error", response.json)
