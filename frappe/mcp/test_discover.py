# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.api import discovery
from frappe.mcp.test_utils import McpTestCase
from frappe.mcp.tools.discover import LAYOUT_FIELDTYPES, PERMISSION_TYPES, SEARCH_LIMIT


class TestDiscover(McpTestCase):
	def discover(self, tool, arguments=None):
		return self.request(
			{
				"jsonrpc": "2.0",
				"id": 1,
				"method": "tools/call",
				"params": {"name": tool, "arguments": arguments or {}},
			}
		)

	def result(self, tool, arguments=None):
		response = self.discover(tool, arguments)
		self.assertEqual(response.status_code, 200)
		self.assertFalse(response.json["result"]["isError"], response.json["result"])
		return response.json["result"]["structuredContent"]

	@contextmanager
	def manager(self):
		user, authorization = self.create_user("MCP Manager")
		frappe.get_doc("User", user).add_roles("System Manager")
		original = self.authorization
		self.authorization = authorization
		try:
			yield
		finally:
			self.authorization = original

	@contextmanager
	def method_cache(self):
		values = {
			discovery.PYTHON_METHOD_CACHE_KEY: [{"path": "frappe.client.get_count", "kind": "rpc"}],
			discovery.PYTHON_SEARCH_CACHE_KEY: [
				{"method": {"path": "frappe.client.get_count"}, "haystack": "frappe.client.get_count"}
			],
			discovery.DOCTYPE_METHOD_CACHE_KEY: [],
			discovery.DOCTYPE_SEARCH_CACHE_KEY: [],
		}
		original = {key: frappe.cache.get_value(key, expires=True) for key in values}
		try:
			for key, value in values.items():
				frappe.cache.set_value(key, value, expires_in_sec=discovery.CACHE_TTL)
			yield
		finally:
			for key, value in original.items():
				if value is None:
					frappe.cache.delete_value(key)
				else:
					frappe.cache.set_value(key, value, expires_in_sec=discovery.CACHE_TTL)

	def test_doctype_search_does_not_search_methods(self):
		with patch("frappe.api.discovery.search") as methods:
			result = self.result("search_doctypes", {"query": "ToDo"})
		self.assertIn("ToDo", result["result"])
		methods.assert_not_called()

	def test_search_matches_any_query(self):
		result = self.result("search_doctypes", {"query": ["ToDo", "Note"]})["result"]
		self.assertIn("ToDo", result)
		self.assertIn("Note", result)
		self.assertTrue(all("todo" in name.lower() or "note" in name.lower() for name in result))

	def test_schema_fields_and_permissions(self):
		result = self.result("get_doctype_schema", {"doctype": "ToDo"})
		self.assertEqual(result["title_field"], "description")
		fields = {field["fieldname"]: field for field in result["fields"]}
		self.assertEqual(fields["allocated_to"]["options"], "User")
		self.assertTrue(fields["assignment_rule"]["read_only"])
		self.assertFalse(set(field["fieldtype"] for field in result["fields"]) & LAYOUT_FIELDTYPES)
		self.assertEqual(set(result["permissions"]), set(PERMISSION_TYPES))
		self.assertTrue(result["permissions"]["read"])

	def test_broad_schema_does_not_expose_records(self):
		result = self.result("get_doctype_schema", {"doctype": "OAuth Bearer Token"})
		self.assertFalse(result["permissions"]["read"])
		self.assertTrue(result["fields"])

	def test_child_table_fields_are_preserved(self):
		result = self.result("get_doctype_schema", {"doctype": "User"})
		roles = next(field for field in result["fields"] if field["fieldname"] == "roles")
		self.assertEqual(roles["fieldtype"], "Table")
		child = self.result("get_doctype_schema", {"doctype": roles["options"]})
		self.assertTrue(child["is_child_table"])
		self.assertFalse(any(child["permissions"].values()))

	def test_manager_rpc_contract_and_search(self):
		with self.manager(), self.method_cache():
			result = self.result("get_method_schema", {"method": "frappe.client.get_count"})
			self.assertEqual(result["path"], "frappe.client.get_count")
			self.assertIn("doctype", [param["name"] for param in result["params"]])
			self.assertEqual(
				"source" in result, any(frappe.get_hooks("expose_discovery_source", app_name="frappe"))
			)
			result = self.result("search_methods", {"query": "get_count"})
			self.assertIn("frappe.client.get_count", [method["path"] for method in result["result"]])

	def test_manager_document_contract_and_list(self):
		with self.manager():
			result = self.result("get_method_schema", {"doctype": "ToDo", "method": "add_comment"})
			self.assertIn("text", [param["name"] for param in result["params"]])
			self.assertEqual(result["endpoint"], "/api/v2/document/ToDo/{name}/method/add_comment")
			self.assertEqual(result["permission"], {"GET": "read", "POST": "write"})
			result = self.result("list_document_methods", {"doctype": "ToDo"})
			self.assertIn("add_comment", [method["method"] for method in result["result"]])

	def test_invalid_arguments_and_unknown_doctype(self):
		for tool, arguments in (
			("search_doctypes", {"query": []}),
			("search_doctypes", {"query": [""]}),
			("search_doctypes", {"query": ""}),
			("search_doctypes", {"query": ["ToDo"], "module": "Desk"}),
			("search_doctypes", {"limit": 0}),
			("search_doctypes", {"limit": "5"}),
			("get_doctype_schema", {}),
			("get_doctype_schema", {"doctype": 1}),
			("get_doctype_schema", {"doctype": ""}),
			("get_doctype_schema", {"doctype": "ToDo", "method": "add_comment"}),
			("get_doctype_schema", {"doctype": "MCP Nonexistent DocType"}),
			("search_methods", {}),
			("get_method_schema", {}),
			("list_document_methods", {}),
			("get_method_schema", {"doctype": "ToDo"}),
			("get_method_schema", {"doctype": "", "method": "add_comment"}),
			("get_method_schema", {"doctype": 1, "method": "add_comment"}),
			("get_method_schema", {"doctype": "ToDo", "method": ""}),
		):
			with self.subTest(tool=tool, arguments=arguments):
				self.assertTrue(self.discover(tool, arguments).json["result"]["isError"])

	def test_discovery_tools_are_read_only(self):
		response = self.request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
		definitions = {tool["name"]: tool for tool in response.json["result"]["tools"]}
		for name in (
			"search_doctypes",
			"get_doctype_schema",
			"search_methods",
			"get_method_schema",
			"list_document_methods",
		):
			self.assertTrue(definitions[name]["annotations"]["readOnlyHint"])

	def test_unavailable_method_index_does_not_block_doctype_search(self):
		with (
			self.manager(),
			patch(
				"frappe.api.discovery.search",
				side_effect=discovery.DiscoveryCacheUnavailable("Index is being generated"),
			),
		):
			self.assertTrue(self.discover("search_methods", {"query": "ToDo"}).json["result"]["isError"])
			result = self.result("search_doctypes", {"query": ["ToDo"]})
		self.assertIn("ToDo", result["result"])

	def test_manager_cannot_discover_nonwhitelisted_methods(self):
		with self.manager(), self.method_cache():
			for arguments in (
				{"method": "frappe.get_roles"},
				{"method": "frappe.mcp.nonexistent"},
				{"doctype": "ToDo", "method": "save"},
				{"doctype": "ToDo", "method": "frappe.client.get_count"},
			):
				with self.subTest(arguments=arguments):
					self.assertTrue(self.discover("get_method_schema", arguments).json["result"]["isError"])

	def test_method_source_respects_app_opt_out(self):
		original_get_hooks = frappe.get_hooks

		def get_hooks(hook=None, *args, **kwargs):
			if hook == "expose_discovery_source":
				return []
			return original_get_hooks(hook, *args, **kwargs)

		with self.manager(), self.method_cache(), patch("frappe.get_hooks", get_hooks):
			result = self.result("get_method_schema", {"method": "frappe.client.get_count"})
		self.assertNotIn("source", result)

	def test_search_is_bounded_and_sorted(self):
		names = self.result("search_doctypes", {"query": ["%"]})["result"]
		self.assertEqual(len(names), SEARCH_LIMIT)
		# Database collation can sort mixed-case names differently from Python.
		expected = frappe.get_all(
			"DocType", filters={"name": ["in", names]}, pluck="name", order_by="name asc"
		)
		self.assertEqual(names, expected)

	def test_search_limit(self):
		self.assertEqual(len(self.result("search_doctypes", {"limit": 5})["result"]), 5)
