# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.api import discovery
from frappe.core.doctype.user.user import generate_keys
from frappe.mcp.test_utils import McpTestCase
from frappe.mcp.tools.discover import LAYOUT_FIELDTYPES, PERMISSION_TYPES


class TestDiscover(McpTestCase):
	def discover(self, arguments=None):
		return self.request(
			{
				"jsonrpc": "2.0",
				"id": 1,
				"method": "tools/call",
				"params": {"name": "discover", "arguments": arguments or {}},
			}
		)

	def result(self, arguments=None):
		response = self.discover(arguments)
		self.assertEqual(response.status_code, 200)
		self.assertFalse(response.json["result"]["isError"], response.json["result"])
		return response.json["result"]["structuredContent"]

	@contextmanager
	def manager(self):
		user = "mcp.manager@example.com"
		if not frappe.db.exists("User", user):
			frappe.get_doc(
				doctype="User", email=user, first_name="MCP Manager", send_welcome_email=0
			).insert()
		frappe.get_doc("User", user).add_roles("System Manager")
		keys = generate_keys(user)
		original = self.authorization
		self.authorization = f"token {keys['api_key']}:{keys['api_secret']}"
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

	def test_site_summary(self):
		result = self.result()
		self.assertEqual(result["type"], "site")
		self.assertEqual(result["site"], self.site)
		self.assertEqual(result["user"], self.user)
		self.assertNotIn("System Manager", result["roles"])
		self.assertEqual(result["counts"]["modules"], len(result["modules"]))
		self.assertIn("Desk", result["modules"])

	def test_search_and_method_restriction(self):
		result = self.result({"query": "ToDo"})
		self.assertIn("ToDo", [row["name"] for row in result["doctypes"]])
		self.assertIn("System Manager", result["methods_unavailable"])
		self.assertNotIn("methods", result)

	def test_schema_fields_and_permissions(self):
		result = self.result({"doctype": "ToDo"})
		self.assertEqual(result["doctype"], "ToDo")
		self.assertEqual(result["title_field"], "description")
		fields = {field["fieldname"]: field for field in result["fields"]}
		self.assertEqual(fields["allocated_to"]["options"], "User")
		self.assertTrue(fields["assignment_rule"]["read_only"])
		self.assertFalse(set(field["fieldtype"] for field in result["fields"]) & LAYOUT_FIELDTYPES)
		self.assertEqual(set(result["permissions"]), set(PERMISSION_TYPES))
		self.assertTrue(result["permissions"]["read"])
		self.assertIn("methods_unavailable", result)

	def test_broad_schema_does_not_expose_records(self):
		result = self.result({"doctype": "OAuth Bearer Token"})
		self.assertEqual(result["doctype"], "OAuth Bearer Token")
		self.assertFalse(result["permissions"]["read"])
		self.assertNotIn("docs", result)
		self.assertNotIn("data", result)
		self.assertTrue(result["fields"])

	def test_child_table_fields_are_preserved(self):
		result = self.result({"doctype": "User"})
		roles = next(field for field in result["fields"] if field["fieldname"] == "roles")
		self.assertEqual(roles["fieldtype"], "Table")
		self.assertEqual(roles["options"], "Has Role")
		with self.manager():
			child = self.result({"doctype": roles["options"]})
		self.assertTrue(child["is_child_table"])
		self.assertEqual(child["methods"], [])
		self.assertFalse(any(child["permissions"].values()))

	def test_method_contracts_denied_to_normal_user(self):
		for arguments in (
			{"method": "frappe.client.get_count"},
			{"doctype": "ToDo", "method": "add_comment"},
		):
			with self.subTest(arguments=arguments):
				response = self.discover(arguments)
				self.assertTrue(response.json["result"]["isError"])
				self.assertEqual(response.json["result"]["content"][0]["text"], "PermissionError")

	def test_manager_rpc_contract_and_search(self):
		with self.manager(), self.method_cache():
			result = self.result({"method": "frappe.client.get_count"})
			self.assertEqual(result["path"], "frappe.client.get_count")
			self.assertIn("doctype", [param["name"] for param in result["params"]])
			self.assertEqual(
				"source" in result, any(frappe.get_hooks("expose_discovery_source", app_name="frappe"))
			)
			result = self.result({"query": "get_count"})
			self.assertIn("frappe.client.get_count", [method["path"] for method in result["methods"]])

	def test_manager_controller_contract(self):
		with self.manager():
			result = self.result({"doctype": "ToDo", "method": "add_comment"})
			self.assertEqual(result["method"], "add_comment")
			self.assertEqual(result["doctype"], "ToDo")
			result = self.result({"doctype": "ToDo"})
			self.assertIn("add_comment", [method["method"] for method in result["methods"]])

	def test_invalid_arguments_and_unknown_doctype(self):
		for arguments in (
			{"doctype": 1},
			{"query": []},
			{"query": "ToDo", "doctype": "ToDo"},
			{"doctype": ""},
			{"unknown": True},
			{"doctype": "MCP Nonexistent DocType"},
		):
			with self.subTest(arguments=arguments):
				self.assertTrue(self.discover(arguments).json["result"]["isError"])

	def test_schema_listed_by_transport(self):
		response = self.request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
		definition = response.json["result"]["tools"][0]
		self.assertEqual(definition["name"], "discover")
		self.assertFalse(definition["inputSchema"]["additionalProperties"])
		self.assertEqual(set(definition["inputSchema"]["properties"]), {"query", "doctype", "method"})
		self.assertTrue(definition["annotations"]["readOnlyHint"])

	def test_search_preserves_doctypes_when_method_index_unavailable(self):
		with (
			self.manager(),
			patch(
				"frappe.api.discovery.search",
				side_effect=discovery.DiscoveryCacheUnavailable("Index is being generated"),
			),
		):
			result = self.result({"query": "ToDo"})
		self.assertIn("ToDo", [row["name"] for row in result["doctypes"]])
		self.assertEqual(result["methods_unavailable"], "Index is being generated")

	def test_manager_cannot_discover_nonwhitelisted_methods(self):
		with self.manager(), self.method_cache():
			for method in ("frappe.get_roles", "frappe.mcp.nonexistent"):
				with self.subTest(method=method):
					response = self.discover({"method": method})
					self.assertTrue(response.json["result"]["isError"])

	def test_method_source_respects_app_opt_out(self):
		original_get_hooks = frappe.get_hooks

		def get_hooks(hook=None, *args, **kwargs):
			if hook == "expose_discovery_source":
				return []
			return original_get_hooks(hook, *args, **kwargs)

		with self.manager(), self.method_cache(), patch("frappe.get_hooks", get_hooks):
			result = self.result({"method": "frappe.client.get_count"})
		self.assertNotIn("source", result)

	def test_search_is_bounded_and_sorted(self):
		result = self.result({"query": "%"})
		names = [row["name"] for row in result["doctypes"]]
		self.assertLessEqual(len(names), 50)
		self.assertEqual(names, sorted(names))
