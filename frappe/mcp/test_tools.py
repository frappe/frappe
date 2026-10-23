# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
from dataclasses import replace
from datetime import date
from unittest.mock import Mock, patch

from pydantic import Field

import frappe
from frappe.mcp import protocol, tools
from frappe.mcp.test_utils import McpTestCase
from frappe.tests import UnitTestCase


class ExampleArguments(tools.ToolArguments):
	doctype: str
	limit: int = Field(default=20, ge=1)
	args: dict = Field(default_factory=dict)


class TestToolSchema(UnitTestCase):
	def test_schema_matches_validation(self):
		tool = tools.Tool("example", ExampleArguments, Mock())
		schema = tool.input_schema
		self.assertEqual(schema["required"], ["doctype"])
		self.assertFalse(schema["additionalProperties"])
		self.assertEqual(schema["properties"]["limit"]["default"], 20)


class TestToolExecution(McpTestCase):
	def call(self, arguments, handler, *, name="example"):
		tool = tools.Tool("example", ExampleArguments, handler)
		with patch("frappe.mcp.tools.registry", return_value=(tool,)):
			return self.request(
				{
					"jsonrpc": "2.0",
					"id": 1,
					"method": "tools/call",
					"params": {"name": name, "arguments": arguments},
				}
			)

	def test_each_tool_rejects_arguments_from_other_operations(self):
		cases = (
			("search_doctypes", {"method": "frappe.ping"}),
			("get_doctype_schema", {"doctype": "ToDo", "query": "ToDo"}),
			("search_methods", {"query": "ping", "doctype": "ToDo"}),
			("get_method_schema", {"method": "frappe.ping", "args": {}}),
			("list_document_methods", {"doctype": "ToDo", "name": "missing"}),
			("get_method_schema", {"doctype": "ToDo", "method": "add_comment", "args": {}}),
			("list_documents", {"doctype": "ToDo", "name": "missing"}),
			("get_document", {"doctype": "ToDo", "name": "missing", "filters": {}}),
			("count_documents", {"doctype": "ToDo", "limit": 20}),
			("create_document", {"doctype": "ToDo", "data": {}, "name": "missing"}),
			("update_document", {"doctype": "ToDo", "data": {}}),
			("delete_document", {"doctype": "ToDo", "name": "missing", "data": {}}),
			("call_method", {"method": "add_comment", "doctype": "ToDo", "name": "missing"}),
			("call_document_method", {"method": "add_comment", "doctype": "ToDo"}),
		)
		for name, arguments in cases:
			with self.subTest(tool=name):
				handler = Mock()
				tool = next(tool for tool in tools.registry() if tool.name == name)
				with patch("frappe.mcp.tools.registry", return_value=(replace(tool, handler=handler),)):
					response = self.request(
						{
							"jsonrpc": "2.0",
							"id": 1,
							"method": "tools/call",
							"params": {"name": name, "arguments": arguments},
						}
					)
				self.assertTrue(response.json["result"]["isError"])
				handler.assert_not_called()

	def test_invalid_arguments_do_not_execute(self):
		cases = (
			{},
			{"doctype": 1},
			{"doctype": "ToDo", "limit": "20"},
			{"doctype": "ToDo", "limit": True},
			{"doctype": "ToDo", "limt": 20},
			{"doctype": "ToDo", "limit": 0},
			{"doctype": "ToDo", "args": []},
			None,
			[],
		)
		for arguments in cases:
			with self.subTest(arguments=arguments):
				handler = Mock()
				response = self.call(arguments, handler)
				self.assertEqual(response.status_code, 200)
				self.assertTrue(response.json["result"]["isError"])
				handler.assert_not_called()

	def test_success_and_default_arguments(self):
		handler = Mock(return_value={"date": date(2026, 1, 1)})
		response = self.call({"doctype": "ToDo"}, handler)
		result = response.json["result"]
		self.assertFalse(result["isError"])
		self.assertEqual(result["structuredContent"], {"date": "2026-01-01"})
		self.assertEqual(json.loads(result["content"][0]["text"]), result["structuredContent"])
		handler.assert_called_once_with(doctype="ToDo", limit=20, args={})

	def test_non_object_result(self):
		response = self.call({"doctype": "ToDo"}, Mock(return_value=[1, 2]))
		self.assertEqual(response.json["result"]["structuredContent"], {"result": [1, 2]})

	def test_unknown_or_missing_tool(self):
		response = self.call({}, Mock(), name="missing")
		self.assertEqual(response.json["error"]["code"], protocol.METHOD_NOT_FOUND)
		response = self.request({"jsonrpc": "2.0", "id": 1, "method": "tools/call"})
		self.assertEqual(response.json["error"]["code"], protocol.INVALID_PARAMS)

	def test_failure_rolls_back_document_write(self):
		def handler(**kwargs):
			frappe.get_doc(doctype="ToDo", description="MCP failed tool fixture").insert()
			frappe.throw("<b>Tool failed</b>")

		response = self.call({"doctype": "ToDo"}, handler)
		self.assertTrue(response.json["result"]["isError"])
		self.assertEqual(response.json["result"]["content"][0]["text"], "Tool failed")
		self.assertFalse(frappe.db.exists("ToDo", {"description": "MCP failed tool fixture"}))

	def test_serialization_failure_rolls_back_write(self):
		def handler(**kwargs):
			frappe.get_doc(doctype="ToDo", description="MCP serialization fixture").insert()
			return {"value": float("nan")}

		response = self.call({"doctype": "ToDo"}, handler)
		self.assertTrue(response.json["result"]["isError"])
		self.assertFalse(frappe.db.exists("ToDo", {"description": "MCP serialization fixture"}))

	def test_permission_failure_is_tool_error(self):
		def handler(**kwargs):
			self.assertEqual(frappe.session.user, self.user)
			frappe.only_for("System Manager")

		response = self.call({"doctype": "ToDo"}, handler)
		self.assertTrue(response.json["result"]["isError"])

	def test_request_state_is_restored(self):
		original_arguments = frappe.local.form_dict
		original_response = frappe.local.response
		for fail in (False, True):
			with self.subTest(fail=fail):
				try:
					with tools.form_dict({"doctype": "ToDo"}):
						self.assertEqual(frappe.form_dict.doctype, "ToDo")
						self.assertEqual(frappe.response.docs, [])
						frappe.response["http_status_code"] = 500
						if fail:
							raise ValueError("failure")
				except ValueError:
					pass
				self.assertIs(frappe.local.form_dict, original_arguments)
				self.assertIs(frappe.local.response, original_response)

	def test_successful_write_is_committed(self):
		def handler(**kwargs):
			return {
				"name": frappe.get_doc(doctype="ToDo", description="MCP successful tool fixture")
				.insert()
				.name
			}

		response = self.call({"doctype": "ToDo"}, handler)
		self.assertFalse(response.json["result"]["isError"])
		name = response.json["result"]["structuredContent"]["name"]
		try:
			self.assertTrue(frappe.db.exists("ToDo", name))
		finally:
			frappe.delete_doc("ToDo", name)
			frappe.db.commit()  # nosemgrep

	def test_modern_tool_call(self):
		tool = tools.Tool("example", ExampleArguments, Mock(return_value={"ok": True}))
		with patch("frappe.mcp.tools.registry", return_value=(tool,)):
			response = self.request(
				{
					"jsonrpc": "2.0",
					"id": 1,
					"method": "tools/call",
					"params": {
						"name": "example",
						"arguments": {"doctype": "ToDo"},
						"_meta": {
							protocol.META_VERSION: protocol.LATEST_VERSION,
							protocol.META_CAPABILITIES: {},
						},
					},
				},
				headers={
					"MCP-Protocol-Version": protocol.LATEST_VERSION,
					"Mcp-Method": "tools/call",
					"Mcp-Name": "example",
				},
			)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["result"]["structuredContent"], {"ok": True})
		self.assertEqual(response.json["result"]["resultType"], "complete")
