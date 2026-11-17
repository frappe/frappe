# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from unittest.mock import Mock, patch

import frappe
from frappe.core.doctype.user.user import User
from frappe.desk.doctype.todo.todo import ToDo
from frappe.email.doctype.email_template.email_template import EmailTemplate
from frappe.mcp.test_utils import McpTestCase
from frappe.tests.utils import whitelist_for_tests


class TestCallMethod(McpTestCase):
	def setUp(self):
		super().setUp()
		self.names = []
		for allocated_to in (self.user, None):
			doc = frappe.get_doc(
				doctype="ToDo", description="MCP method fixture", allocated_to=allocated_to
			).insert()
			self.names.append(doc.name)
		self.own, self.private = self.names

	def tearDown(self):
		try:
			frappe.set_user("Administrator")
			for name in self.names:
				frappe.delete_doc_if_exists("ToDo", name)
			frappe.db.commit()  # nosemgrep
		finally:
			super().tearDown()

	def invoke(self, *, tool="call_method", **arguments):
		return self.request(
			{
				"jsonrpc": "2.0",
				"id": 1,
				"method": "tools/call",
				"params": {"name": tool, "arguments": arguments},
			}
		)

	def result(self, **arguments):
		response = self.invoke(**arguments)
		self.assertEqual(response.status_code, 200)
		self.assertFalse(response.json["result"]["isError"], response.json["result"])
		return response.json["result"]["structuredContent"]

	def test_rpc(self):
		result = self.result(
			method="frappe.client.get_count", args={"doctype": "ToDo", "filters": {"name": self.own}}
		)
		self.assertEqual(result["result"], 1)

	def test_rpc_preserves_document_permissions(self):
		response = self.invoke(method="frappe.client.get", args={"doctype": "ToDo", "name": self.private})
		self.assertTrue(response.json["result"]["isError"])

	def test_controller_module_function(self):
		description = f"MCP module call {self.own}"
		result = self.result(
			method="frappe.desk.doctype.todo.todo.new_todo", args={"description": description}
		)
		self.assertIsNone(result["result"])
		name = frappe.db.get_value("ToDo", {"description": description, "owner": self.user}, "name")
		self.assertIsNotNone(name)
		self.names.append(name)
		self.assertEqual(frappe.db.get_value("ToDo", name, "owner"), self.user)

	def test_document_method(self):
		result = self.result(
			tool="call_document_method",
			doctype="ToDo",
			name=self.own,
			method="add_comment",
			args={"text": "MCP comment"},
		)
		self.assertEqual(result["document"]["name"], self.own)
		self.assertEqual(result["result"]["reference_name"], self.own)
		self.assertEqual(result["result"]["content"], "MCP comment")

	def test_private_document_method_is_denied(self):
		response = self.invoke(
			tool="call_document_method",
			doctype="ToDo",
			name=self.private,
			method="add_comment",
			args={"text": "Forbidden"},
		)
		self.assertTrue(response.json["result"]["isError"])
		self.assertFalse(
			frappe.db.exists("Comment", {"reference_name": self.private, "content": "Forbidden"})
		)

	def test_non_whitelisted_and_uninstalled_methods(self):
		for arguments in (
			{"method": "frappe.get_all", "args": {"doctype": "User"}},
			{"method": "missing_app.api.method"},
			{"tool": "call_document_method", "doctype": "ToDo", "name": self.own, "method": "save"},
		):
			with self.subTest(arguments=arguments):
				self.assertTrue(self.invoke(**arguments).json["result"]["isError"])

	def test_invalid_arguments_never_dispatch(self):
		with patch("frappe.api.v2.handle_rpc_call") as rpc, patch("frappe.api.v2.execute_doc_method") as doc:
			for arguments in (
				{},
				{"method": ""},
				{"method": ["frappe.ping"]},
				{"method": "frappe.ping", "args": []},
				{"method": "frappe.ping", "args": None},
				{"tool": "call_document_method", "method": "add_comment", "name": self.own},
				{"method": "frappe.ping", "ignore_permissions": True},
			):
				with self.subTest(arguments=arguments):
					self.assertTrue(self.invoke(**arguments).json["result"]["isError"])
			rpc.assert_not_called()
			doc.assert_not_called()

	def test_method_argument_validation(self):
		for args in ({}, {"value": {"unexpected": "object"}}):
			with self.subTest(args=args):
				response = self.invoke(method=f"{__name__}.typed_method", args=args)
				self.assertTrue(response.json["result"]["isError"])

	def test_methods_without_get_or_post_are_denied(self):
		response = self.invoke(method=f"{__name__}.delete_method")
		self.assertEqual(response.json["result"]["content"][0]["text"], "Not permitted")

	def test_get_only_method_runs_as_get(self):
		result = self.result(method=f"{__name__}.get_method")
		self.assertEqual(result["result"], "GET")

	def test_get_only_document_method_needs_read_permission(self):
		# Desk User reads Email Template but cannot write it.
		template = frappe.get_doc(
			doctype="Email Template", name=f"MCP {frappe.generate_hash(length=10)}", subject="MCP"
		).insert()
		self.addCleanup(frappe.delete_doc_if_exists, "Email Template", template.name)
		for method, expected in (("mcp_get", "GET"), ("mcp_post", None)):
			with self.subTest(method=method):
				with (
					patch.object(EmailTemplate, "mcp_get", get_document_method, create=True),
					patch.object(EmailTemplate, "mcp_post", post_document_method, create=True),
				):
					response = self.invoke(
						tool="call_document_method",
						doctype="Email Template",
						name=template.name,
						method=method,
					)
				result = response.json["result"]
				self.assertEqual(result["isError"], expected is None, result)
				if expected:
					self.assertEqual(result["structuredContent"]["result"], expected)

	def test_get_only_method_writes_roll_back(self):
		result = self.result(method=f"{__name__}.get_write_method", args={"name": self.own})
		self.assertEqual(result["result"], "Written in GET")
		self.assertEqual(frappe.db.get_value("ToDo", self.own, "description"), "MCP method fixture")

	def test_document_method_needs_write_permission(self):
		frappe.share.add("ToDo", self.private, user=self.user, read=1, write=0, notify=0)
		response = self.invoke(
			tool="call_document_method",
			doctype="ToDo",
			name=self.private,
			method="add_comment",
			args={"text": "No write access"},
		)
		self.assertTrue(response.json["result"]["isError"])

	def test_override_whitelisted_method(self):
		original = frappe.get_hooks
		with patch("frappe.get_hooks", wraps=original) as hooks:
			# Only replace the override hook; permission and document hooks stay real.
			hooks.side_effect = lambda hook=None, *a, **kw: (
				{"frappe.ping": [f"{__name__}.post_method"]}
				if hook == "override_whitelisted_methods"
				else original(hook, *a, **kw)
			)
			result = self.result(method="frappe.ping")
		self.assertEqual(result["result"]["user"], self.user)

	def test_failed_method_rolls_back_and_discards_callback(self):
		callback = Mock()
		with patch("frappe.mcp.test_methods.commit_callback", callback):
			response = self.invoke(method=f"{__name__}.failing_method", args={"name": self.own})
		self.assertTrue(response.json["result"]["isError"])
		self.assertEqual(frappe.db.get_value("ToDo", self.own, "description"), "MCP method fixture")
		callback.assert_not_called()

	def test_rpc_rest_parity(self):
		args = {"doctype": "ToDo", "filters": {"name": self.own}}
		result = self.result(method="frappe.client.get_count", args=args)
		response = self.request(args, path="/api/v2/method/frappe.client.get_count")
		self.assertEqual(response.status_code, 200)
		self.assertEqual(result["result"], response.json["data"])

	def test_server_script_response_and_dispatch(self):
		def run_script(script):
			self.assertEqual(script, "MCP test script")
			frappe.response.message = {"user": frappe.session.user, "value": frappe.form_dict.value}
			frappe.response.http_status_code = 202

		mapping = {"_api": {"mcp_test_script": "MCP test script"}}
		with (
			patch("frappe.api.v2.get_server_script_map", return_value=mapping),
			patch("frappe.api.v2.run_server_script", side_effect=run_script),
		):
			result = self.result(method="mcp_test_script", args={"value": "Script argument"})
		self.assertEqual(result["result"], {"user": self.user, "value": "Script argument"})

	def test_serialization_failure_rolls_back_method(self):
		response = self.invoke(method=f"{__name__}.unserializable_method", args={"name": self.own})
		self.assertTrue(response.json["result"]["isError"])
		self.assertEqual(frappe.db.get_value("ToDo", self.own, "description"), "MCP method fixture")

	def test_document_fields_are_filtered(self):
		frappe.share.add("User", self.user, user=self.user, read=1, write=1, notify=0)
		with patch.object(User, "mcp_post", post_document_method, create=True):
			result = self.result(
				tool="call_document_method", doctype="User", name=self.user, method="mcp_post"
			)
		self.assertIsNone(result["document"].get("api_key"))
		self.assertIsNone(result["document"].get("api_secret"))

	def test_submit_retains_operation_permissions(self):
		response = self.invoke(tool="call_document_method", doctype="ToDo", name=self.own, method="submit")
		self.assertTrue(response.json["result"]["isError"])
		self.assertEqual(frappe.db.get_value("ToDo", self.own, "docstatus"), 0)

	def test_rpc_response_and_success_callback(self):
		callback = Mock()
		with patch("frappe.mcp.test_methods.commit_callback", callback):
			result = self.result(method=f"{__name__}.response_method", args={"value": "Response value"})
		self.assertEqual(result["result"], "Response value")
		callback.assert_called_once_with()

	def test_explicit_commit_succeeds(self):
		callback = Mock()
		with patch(f"{__name__}.commit_callback", callback):
			result = self.result(method=f"{__name__}.transaction_method", args={"name": self.own})
		self.assertEqual(result["result"], "commit")
		self.assertEqual(frappe.db.get_value("ToDo", self.own, "description"), "Explicit transaction")
		callback.assert_called_once_with()

	def test_explicit_rollback_succeeds(self):
		callback = Mock()
		with patch(f"{__name__}.commit_callback", callback):
			result = self.result(
				method=f"{__name__}.transaction_method", args={"name": self.own, "operation": "rollback"}
			)
		self.assertEqual(result["result"], "rollback")
		self.assertEqual(frappe.db.get_value("ToDo", self.own, "description"), "MCP method fixture")
		callback.assert_not_called()

	def test_failure_after_commit_rolls_back_pending_work(self):
		callback = Mock()
		with patch(f"{__name__}.commit_callback", callback):
			response = self.invoke(
				method=f"{__name__}.transaction_method", args={"name": self.own, "fail": True}
			)
		self.assertTrue(response.json["result"]["isError"])
		self.assertEqual(response.json["result"]["content"][0]["text"], "Failure after transaction")
		self.assertEqual(frappe.db.get_value("ToDo", self.own, "description"), "Explicit transaction")
		callback.assert_called_once_with()

	def test_failure_after_rollback_rolls_back_pending_work(self):
		callback = Mock()
		with patch(f"{__name__}.commit_callback", callback):
			response = self.invoke(
				method=f"{__name__}.transaction_method",
				args={"name": self.own, "operation": "rollback", "fail": True},
			)
		self.assertTrue(response.json["result"]["isError"])
		self.assertEqual(response.json["result"]["content"][0]["text"], "Failure after transaction")
		self.assertEqual(frappe.db.get_value("ToDo", self.own, "description"), "MCP method fixture")
		callback.assert_not_called()


@whitelist_for_tests(methods=["POST"])
def typed_method(value: int):
	return value


@whitelist_for_tests(methods=["POST"])
def post_method():
	return {"user": frappe.session.user}


@whitelist_for_tests(methods=["GET"])
def get_method():
	return frappe.request.method


@whitelist_for_tests(methods=["GET"])
def get_write_method(name: str):
	doc = frappe.get_doc("ToDo", name)
	doc.description = "Written in GET"
	doc.save()
	return doc.description


@whitelist_for_tests(methods=["DELETE"])
def delete_method():
	raise AssertionError("Unsupported method must never run")


@whitelist_for_tests(methods=["GET"])
def get_document_method(self):
	return frappe.request.method


@whitelist_for_tests(methods=["POST"])
def post_document_method(self):
	return frappe.request.method


@whitelist_for_tests(methods=["POST"])
def failing_method(name: str):
	doc = frappe.get_doc("ToDo", name)
	doc.description = "Failed MCP method"
	doc.save()
	frappe.db.after_commit.add(commit_callback)
	frappe.throw("Method failed")


def commit_callback():
	raise AssertionError("Failed method's commit callback must never run")


@whitelist_for_tests(methods=["POST"])
def unserializable_method(name: str):
	doc = frappe.get_doc("ToDo", name)
	doc.description = "Failed serialization"
	doc.save()
	return float("nan")


@whitelist_for_tests(methods=["POST"])
def response_method(value: str):
	frappe.response.message = value
	frappe.response.http_status_code = 202
	frappe.db.after_commit.add(commit_callback)


@whitelist_for_tests(methods=["POST"])
def transaction_method(name: str, operation: str = "commit", fail: bool = False):
	doc = frappe.get_doc("ToDo", name)
	doc.description = "Explicit transaction"
	doc.save()
	frappe.db.after_commit.add(commit_callback)
	if operation == "commit":
		frappe.db.commit()  # nosemgrep
	else:
		frappe.db.rollback()
	if fail:
		doc.reload()
		doc.description = "Pending after transaction"
		doc.save()
		frappe.db.after_commit.add(commit_callback)
		frappe.throw("Failure after transaction")
	return operation
