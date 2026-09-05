# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import base64
import json

from werkzeug.test import TestResponse

import frappe
from frappe.mcp.protocol import (
	HANDSHAKE_VERSION,
	HEADER_MISMATCH,
	META_PROTOCOL_VERSION,
	METHOD_NOT_FOUND,
	PROTOCOL_VERSION,
	SUPPORTED_VERSIONS,
	UNSUPPORTED_PROTOCOL_VERSION,
)
from frappe.tests.test_api import FrappeAPITestCase, make_request
from frappe.tests.utils import whitelist_for_tests

MCP_PATH = "/api/mcp"


@whitelist_for_tests(methods=["GET"])
def read_only_method(value: str = "read"):
	"""A GET-only whitelisted method, to prove the HTTP method mapping."""
	return value


@whitelist_for_tests(methods=["POST"])
def write_then_fail(description: str):
	"""Write a document and then fail, to prove the savepoint rolls the write back."""
	frappe.get_doc({"doctype": "ToDo", "description": description}).insert()
	frappe.throw("Deliberate failure")


class TestMCP(FrappeAPITestCase):
	TEST_USER = "mcp@example.com"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.get_doc(
			{
				"doctype": "User",
				"email": cls.TEST_USER,
				"first_name": "MCP",
				"send_welcome_email": 0,
				"roles": [],
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
		frappe.delete_doc_if_exists("User", cls.TEST_USER)
		frappe.db.commit()

	# Helpers

	def sid_for(self, user: str) -> str:
		from frappe.auth import CookieManager, LoginManager
		from frappe.utils import set_request

		original_request = getattr(frappe.local, "request", None)
		set_request(path="/")
		try:
			frappe.local.cookie_manager = CookieManager()
			frappe.local.login_manager = LoginManager()
			frappe.local.login_manager.login_as(user)
			return frappe.session.sid
		finally:
			frappe.local.request = original_request
			frappe.set_user("Administrator")

	def rpc(
		self,
		method: str,
		params: dict | None = None,
		id: int | None = 1,
		headers: dict | None = None,
		sid: str | None = "administrator",
	) -> TestResponse:
		params = {} if params is None else dict(params)
		params.setdefault("_meta", {}).setdefault(META_PROTOCOL_VERSION, PROTOCOL_VERSION)

		body = {"jsonrpc": "2.0", "method": method, "params": params}
		if id is not None:
			body["id"] = id

		request_headers = {
			"MCP-Protocol-Version": PROTOCOL_VERSION,
			"Mcp-Method": method,
			"Accept": "application/json, text/event-stream",
		}
		if method == "tools/call" and params.get("name"):
			request_headers["Mcp-Name"] = params["name"]
		request_headers.update(headers or {})
		request_headers = {key: value for key, value in request_headers.items() if value is not None}

		if sid == "administrator":
			sid = self.sid
		if sid:
			self.TEST_CLIENT.set_cookie("sid", sid)
		else:
			self.TEST_CLIENT.delete_cookie("sid")

		return make_request(
			target=self.TEST_CLIENT.post,
			args=(MCP_PATH,),
			kwargs={"json": body, "headers": request_headers},
		)

	def call_tool(self, name: str, arguments: dict | None = None, **kwargs) -> TestResponse:
		return self.rpc("tools/call", {"name": name, "arguments": arguments or {}}, **kwargs)

	def assertToolError(self, response: TestResponse) -> str:
		self.assertEqual(response.status_code, 200)
		result = response.json["result"]
		self.assertTrue(result["isError"], msg=json.dumps(result))

		message = result["content"][0]["text"]
		self.assertTrue(message)
		self.assertNotIn("<", message, msg="the message must carry no markup")
		self.assertNotIn("Traceback", message)
		return message

	def track(self, doctype: str, name: str) -> None:
		"""Delete a document that a request committed, once this test is done."""

		def cleanup():
			# The request wrote on another connection. Refresh this one's snapshot.
			frappe.db.rollback()
			frappe.delete_doc_if_exists(doctype, name)
			frappe.db.commit()

		self.addCleanup(cleanup)

	def create_todo(self, description: str) -> str:
		"""Create through the tool, so that every write happens on the request's connection."""
		result = self.assertToolSuccess(
			self.call_tool(
				"write_document",
				{"action": "create", "doctype": "ToDo", "data": {"description": description}},
			)
		)
		name = result["document"]["name"]
		self.track("ToDo", name)
		return name

	def assertToolSuccess(self, response: TestResponse) -> dict:
		self.assertEqual(response.status_code, 200)
		result = response.json["result"]
		self.assertFalse(result["isError"], msg=json.dumps(result))
		return result["structuredContent"]

	# server/discover

	def test_discover_reports_the_server(self):
		response = self.rpc("server/discover")
		self.assertEqual(response.status_code, 200)

		result = response.json["result"]
		self.assertEqual(result["supportedVersions"], list(SUPPORTED_VERSIONS))
		self.assertIn("tools", result["capabilities"])
		self.assertEqual(result["serverInfo"]["name"], "frappe")
		self.assertEqual(result["serverInfo"]["version"], frappe.__version__)
		self.assertIn("discover", result["instructions"])
		self.assertEqual(result["resultType"], "complete")
		self.assertEqual(result["cacheScope"], "public")
		self.assertIn("ttlMs", result)

	# Transport

	def test_get_and_delete_are_not_allowed(self):
		for method in (self.TEST_CLIENT.get, self.TEST_CLIENT.delete):
			response = make_request(target=method, args=(MCP_PATH,))
			self.assertEqual(response.status_code, 405)

	def test_notification_is_accepted_without_a_body(self):
		response = self.rpc("server/discover", id=None)
		self.assertEqual(response.status_code, 202)
		self.assertEqual(response.data, b"")

	def test_guest_is_challenged(self):
		with self.change_settings("OAuth Settings", commit=True, show_protected_resource_metadata=1):
			response = self.rpc("server/discover", sid=None)

		self.assertEqual(response.status_code, 401)
		self.assertIn(
			"/.well-known/oauth-protected-resource",
			response.headers["WWW-Authenticate"],
		)

	def test_unknown_rpc_method(self):
		response = self.rpc("tools/nope")
		self.assertEqual(response.status_code, 404)
		self.assertEqual(response.json["error"]["code"], METHOD_NOT_FOUND)

	# Protocol revisions

	def handshake_rpc(
		self, method: str, params: dict | None = None, id: int | None = 1, headers: dict | None = None
	):
		"""A request as the handshake revision sends it: no transport headers."""
		bare = {"MCP-Protocol-Version": None, "Mcp-Method": None, "Mcp-Name": None}
		return self.rpc(method, params, id=id, headers={**bare, **(headers or {})})

	def test_initialize_negotiates_the_requested_version(self):
		response = self.handshake_rpc(
			"initialize",
			{
				"protocolVersion": HANDSHAKE_VERSION,
				"capabilities": {},
				"clientInfo": {"name": "test-client", "version": "1"},
			},
			id=0,
		)
		self.assertEqual(response.status_code, 200)

		result = response.json["result"]
		self.assertEqual(result["protocolVersion"], HANDSHAKE_VERSION)
		self.assertIn("tools", result["capabilities"])
		self.assertEqual(result["serverInfo"]["name"], "frappe")
		self.assertIn("discover", result["instructions"])

		# The handshake revision has neither of these, so they are not sent.
		self.assertNotIn("resultType", result)
		self.assertNotIn("_meta", result)

	def test_initialize_offers_the_newest_version_it_knows(self):
		response = self.handshake_rpc("initialize", {"protocolVersion": "1999-01-01"}, id=0)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["result"]["protocolVersion"], PROTOCOL_VERSION)

	def test_handshake_revision_needs_no_transport_headers(self):
		"""A client cannot send the version header until it knows the version."""
		self.assertEqual(self.handshake_rpc("notifications/initialized", id=None).status_code, 202)
		self.assertEqual(self.handshake_rpc("ping").status_code, 200)

		response = self.handshake_rpc("tools/list", headers={"MCP-Protocol-Version": HANDSHAKE_VERSION})
		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			[tool["name"] for tool in response.json["result"]["tools"]],
			["call_method", "discover", "get_documents", "write_document"],
		)

	def test_handshake_revision_can_call_a_tool(self):
		response = self.rpc(
			"tools/call",
			{"name": "discover", "arguments": {"doctype": "ToDo"}},
			headers={"MCP-Protocol-Version": HANDSHAKE_VERSION, "Mcp-Method": None, "Mcp-Name": None},
		)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["result"]["structuredContent"]["doctype"], "ToDo")

	def test_unknown_version_header_is_rejected_after_the_handshake(self):
		response = self.rpc("tools/list", headers={"MCP-Protocol-Version": "1999-01-01"})
		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.json["error"]["code"], UNSUPPORTED_PROTOCOL_VERSION)

	def test_missing_protocol_version_header(self):
		"""Without a header the request predates the header, so it is answered as such."""
		response = self.rpc("server/discover", headers={"MCP-Protocol-Version": None, "Mcp-Method": None})
		self.assertEqual(response.status_code, 200)
		self.assertNotIn("resultType", response.json["result"])

	def test_mismatched_method_header(self):
		response = self.rpc("server/discover", headers={"Mcp-Method": "tools/list"})
		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.json["error"]["code"], HEADER_MISMATCH)

	def test_mismatched_name_header(self):
		response = self.call_tool("discover", headers={"Mcp-Name": "get_documents"})
		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.json["error"]["code"], HEADER_MISMATCH)

	def test_base64_name_header(self):
		encoded = base64.b64encode(b"discover").decode()
		response = self.call_tool("discover", headers={"Mcp-Name": f"=?base64?{encoded}?="})
		self.assertEqual(response.status_code, 200)

	def test_unsupported_protocol_version(self):
		response = self.rpc(
			"server/discover",
			params={"_meta": {META_PROTOCOL_VERSION: "2000-01-01"}},
			headers={"MCP-Protocol-Version": "2000-01-01"},
		)
		self.assertEqual(response.status_code, 400)

		error = response.json["error"]
		self.assertEqual(error["code"], UNSUPPORTED_PROTOCOL_VERSION)
		self.assertEqual(error["data"]["supported"], list(SUPPORTED_VERSIONS))
		self.assertEqual(error["data"]["requested"], "2000-01-01")

	def test_origin_is_rejected_when_not_allowed(self):
		from werkzeug.test import EnvironBuilder
		from werkzeug.wrappers import Request

		from frappe.mcp import transport
		from frappe.mcp.protocol import McpError

		def request_from(origin):
			return Request(EnvironBuilder(headers={"Origin": origin}).get_environ())

		frappe.local.allow_cors = "https://allowed.example.com"
		try:
			with self.assertRaises(McpError) as raised:
				transport._check_origin(request_from("https://evil.example.com"))
			self.assertEqual(raised.exception.http_status_code, 403)

			transport._check_origin(request_from("https://allowed.example.com"))
		finally:
			del frappe.local.allow_cors

	# tools/list

	def test_tools_list_is_deterministic(self):
		first = self.rpc("tools/list").json["result"]
		second = self.rpc("tools/list").json["result"]

		self.assertEqual(first["tools"], second["tools"])
		self.assertEqual(first["cacheScope"], "private")
		self.assertEqual(
			[tool["name"] for tool in first["tools"]],
			["call_method", "discover", "get_documents", "write_document"],
		)
		for tool in first["tools"]:
			self.assertIn("inputSchema", tool)
			self.assertIn("description", tool)

	# discover

	def test_discover_site_summary(self):
		result = self.assertToolSuccess(self.call_tool("discover"))
		self.assertEqual(result["type"], "site")
		self.assertIn("Core", result["modules"])

	def test_discover_doctype_schema(self):
		result = self.assertToolSuccess(self.call_tool("discover", {"doctype": "ToDo"}))

		self.assertEqual(result["doctype"], "ToDo")
		self.assertFalse(result["is_submittable"])
		self.assertTrue(result["permissions"]["read"])

		fields = {field["fieldname"]: field for field in result["fields"]}
		self.assertEqual(fields["description"]["fieldtype"], "Text Editor")
		self.assertTrue(fields["description"]["reqd"])
		self.assertNotIn("Section Break", {field["fieldtype"] for field in result["fields"]})

	def test_discover_reports_missing_doctype(self):
		message = self.assertToolError(self.call_tool("discover", {"doctype": "Not A DocType"}))
		self.assertIn("Not A DocType", message)

	def test_discover_without_system_manager(self):
		result = self.assertToolSuccess(
			self.call_tool("discover", {"doctype": "ToDo"}, sid=self.sid_for(self.TEST_USER))
		)
		self.assertIn("methods_unavailable", result)
		self.assertIn("fields", result)

	# get_documents

	def test_get_documents_list(self):
		name = self.create_todo("mcp list")

		result = self.assertToolSuccess(
			self.call_tool(
				"get_documents",
				{"doctype": "ToDo", "filters": {"name": name}, "fields": ["name", "description"]},
			)
		)
		self.assertEqual(result["documents"][0]["name"], name)
		self.assertFalse(result["has_next_page"])

		result = self.assertToolSuccess(self.call_tool("get_documents", {"doctype": "ToDo", "name": name}))
		self.assertEqual(result["document"]["description"], "mcp list")

		result = self.assertToolSuccess(
			self.call_tool("get_documents", {"doctype": "ToDo", "count_only": True})
		)
		self.assertGreaterEqual(result["count"], 1)

	def test_get_documents_needs_permission(self):
		message = self.assertToolError(
			self.call_tool(
				"get_documents",
				{"doctype": "User", "name": "Administrator"},
				sid=self.sid_for(self.TEST_USER),
			)
		)
		self.assertIn("User", message)

	# write_document

	def test_write_document_lifecycle(self):
		name = self.create_todo("mcp write")

		result = self.assertToolSuccess(
			self.call_tool(
				"write_document",
				{"action": "update", "doctype": "ToDo", "name": name, "data": {"status": "Closed"}},
			)
		)
		self.assertEqual(result["document"]["status"], "Closed")

		self.assertToolSuccess(
			self.call_tool("write_document", {"action": "delete", "doctype": "ToDo", "name": name})
		)
		frappe.db.rollback()
		self.assertFalse(frappe.db.exists("ToDo", name))

	def test_write_document_denied_commits_nothing(self):
		role_name = "MCP Denied Role"
		message = self.assertToolError(
			self.call_tool(
				"write_document",
				{"action": "create", "doctype": "Role", "data": {"role_name": role_name}},
				sid=self.sid_for(self.TEST_USER),
			)
		)
		self.assertIn("Role", message)

		frappe.db.rollback()
		self.assertFalse(frappe.db.exists("Role", role_name))

	def test_failed_call_rolls_back_its_writes(self):
		description = "mcp rolled back"
		self.assertToolError(
			self.call_tool(
				"call_method",
				{
					"method": "frappe.tests.test_mcp.write_then_fail",
					"args": {"description": description},
				},
			)
		)
		frappe.db.rollback()
		self.assertFalse(frappe.db.exists("ToDo", {"description": description}))

	# call_method

	def test_call_method_rpc(self):
		result = self.assertToolSuccess(self.call_tool("call_method", {"method": "frappe.ping"}))
		self.assertEqual(result["result"], "pong")

	def test_call_method_allows_a_get_only_method(self):
		"""The endpoint is always POST, so the HTTP method must come from the allow-list."""
		result = self.assertToolSuccess(
			self.call_tool(
				"call_method",
				{"method": "frappe.tests.test_mcp.read_only_method", "args": {"value": "ok"}},
			)
		)
		self.assertEqual(result["result"], "ok")

	def test_call_method_on_a_document(self):
		name = self.create_todo("mcp method")

		result = self.assertToolSuccess(
			self.call_tool(
				"call_method",
				{
					"doctype": "ToDo",
					"name": name,
					"method": "add_comment",
					"args": {"comment_type": "Comment", "text": "from mcp"},
				},
			)
		)
		self.assertEqual(result["document"]["name"], name)

	def test_call_method_refuses_a_method_that_is_not_whitelisted(self):
		message = self.assertToolError(
			self.call_tool("call_method", {"method": "frappe.mcp.tools.methods.call_method"})
		)
		self.assertIn("whitelisted", message)

	def test_call_method_needs_permission(self):
		message = self.assertToolError(
			self.call_tool(
				"call_method",
				{
					"doctype": "User",
					"name": "Administrator",
					"method": "add_comment",
					"args": {"comment_type": "Comment", "text": "from mcp"},
				},
				sid=self.sid_for(self.TEST_USER),
			)
		)
		self.assertIn("User", message)
