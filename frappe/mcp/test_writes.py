# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from unittest.mock import Mock, patch

import frappe
from frappe.api import v2
from frappe.desk.doctype.todo.todo import ToDo
from frappe.mcp.test_utils import McpTestCase


class TestWriteDocument(McpTestCase):
	def setUp(self):
		super().setUp()
		self.names = []
		for allocated_to in (self.user, None):
			doc = frappe.get_doc(
				doctype="ToDo", description="MCP write fixture", allocated_to=allocated_to
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

	def write(self, *, tool="create_document", **arguments):
		return self.request(
			{
				"jsonrpc": "2.0",
				"id": 1,
				"method": "tools/call",
				"params": {"name": tool, "arguments": arguments},
			}
		)

	def result(self, **arguments):
		response = self.write(**arguments)
		self.assertEqual(response.status_code, 200)
		self.assertFalse(response.json["result"]["isError"], response.json["result"])
		result = response.json["result"]["structuredContent"]
		if arguments.get("tool", "create_document") == "create_document":
			self.names.append(result["name"])
		return result

	def test_create(self):
		result = self.result(
			tool="create_document", doctype="ToDo", data={"description": "Created through MCP"}
		)
		self.assertEqual(result["owner"], self.user)
		self.assertEqual(frappe.db.get_value("ToDo", result["name"], "description"), "Created through MCP")

	def test_update(self):
		result = self.result(
			tool="update_document", doctype="ToDo", name=self.own, data={"description": "Updated through MCP"}
		)
		self.assertEqual(result["name"], self.own)
		self.assertEqual(frappe.db.get_value("ToDo", self.own, "description"), "Updated through MCP")

	def test_delete(self):
		result = self.result(tool="delete_document", doctype="ToDo", name=self.own)
		self.assertEqual(result, {"result": None})
		self.assertFalse(frappe.db.exists("ToDo", self.own))

	def test_unauthorized_update_and_delete(self):
		for action in ("update", "delete"):
			arguments = {"tool": f"{action}_document", "doctype": "ToDo", "name": self.private}
			if action == "update":
				arguments["data"] = {"description": "Forbidden update"}
			response = self.write(**arguments)
			self.assertTrue(response.json["result"]["isError"])
			self.assertEqual(frappe.db.get_value("ToDo", self.private, "description"), "MCP write fixture")

	def test_update_cannot_grant_itself_document_access(self):
		response = self.write(
			tool="update_document", doctype="ToDo", name=self.private, data={"allocated_to": self.user}
		)
		self.assertTrue(response.json["result"]["isError"])
		self.assertIsNone(frappe.db.get_value("ToDo", self.private, "allocated_to"))

	def test_create_requires_doctype_permission(self):
		response = self.write(
			tool="create_document",
			doctype="User",
			data={"email": "mcp.forbidden@example.com", "first_name": "Forbidden"},
		)
		self.assertTrue(response.json["result"]["isError"])
		self.assertFalse(frappe.db.exists("User", "mcp.forbidden@example.com"))

	def test_client_flags_cannot_bypass_permissions(self):
		response = self.write(
			tool="update_document",
			doctype="ToDo",
			name=self.private,
			data={"description": "Forbidden update", "flags": {"ignore_permissions": True}},
		)
		self.assertTrue(response.json["result"]["isError"])
		response = self.write(
			tool="create_document",
			doctype="User",
			data={
				"email": "mcp.forbidden@example.com",
				"first_name": "Forbidden",
				"flags": {"ignore_permissions": True},
			},
		)
		self.assertTrue(response.json["result"]["isError"])
		self.assertFalse(frappe.db.exists("User", "mcp.forbidden@example.com"))

	def test_required_document_fields(self):
		response = self.write(tool="create_document", doctype="ToDo", data={})
		self.assertTrue(response.json["result"]["isError"])
		self.assertIn("description", response.json["result"]["content"][0]["text"])

	def test_frappe_field_validation(self):
		response = self.write(
			tool="update_document", doctype="ToDo", name=self.own, data={"status": "Invalid status"}
		)
		self.assertTrue(response.json["result"]["isError"])
		self.assertEqual(frappe.db.get_value("ToDo", self.own, "status"), "Open")

	def test_invalid_arguments_do_not_execute(self):
		cases = (
			{},
			{"action": "submit", "doctype": "ToDo"},
			{"tool": "create_document", "doctype": "ToDo"},
			{"tool": "update_document", "doctype": "ToDo", "data": {}},
			{"tool": "delete_document", "doctype": "ToDo"},
			{"tool": "create_document", "doctype": "ToDo", "data": []},
			{"tool": "create_document", "doctype": "ToDo", "name": self.own, "data": {}},
			{"tool": "delete_document", "doctype": "ToDo", "name": self.own, "data": {}},
			{"tool": "delete_document", "doctype": "ToDo", "name": self.own, "ignore_permissions": True},
		)
		with (
			patch("frappe.api.v2.create_doc") as create,
			patch("frappe.api.v2.update_doc") as update,
			patch("frappe.api.v2.delete_doc") as delete,
		):
			for arguments in cases:
				with self.subTest(arguments=arguments):
					self.assertTrue(self.write(**arguments).json["result"]["isError"])
			create.assert_not_called()
			update.assert_not_called()
			delete.assert_not_called()

	def test_failed_update_rolls_back_hooks_and_callbacks(self):
		original_on_update = ToDo.on_update
		callback = Mock()
		cleanup = Mock()

		def on_update(doc):
			original_on_update(doc)
			frappe.db.after_commit.add(callback)
			frappe.db.after_rollback.add(cleanup)
			frappe.throw("Update hook failed")

		with patch.object(ToDo, "on_update", on_update):
			response = self.write(
				tool="update_document",
				doctype="ToDo",
				name=self.own,
				data={"description": "Rolled back update"},
			)
		self.assertTrue(response.json["result"]["isError"])
		self.assertEqual(frappe.db.get_value("ToDo", self.own, "description"), "MCP write fixture")
		callback.assert_not_called()
		cleanup.assert_called_once_with()

	def test_failed_delete_preserves_document(self):
		with patch.object(
			ToDo, "after_delete", side_effect=frappe.ValidationError("Delete hook failed"), create=True
		):
			response = self.write(tool="delete_document", doctype="ToDo", name=self.own)
		self.assertTrue(response.json["result"]["isError"])
		self.assertTrue(frappe.db.exists("ToDo", self.own))

	def test_serialization_failure_rolls_back_update(self):
		original_update = v2.update_doc

		def update(doctype, name):
			original_update(doctype, name)
			return {"value": float("nan")}

		with patch("frappe.api.v2.update_doc", update):
			response = self.write(
				tool="update_document",
				doctype="ToDo",
				name=self.own,
				data={"description": "Rolled back update"},
			)
		self.assertTrue(response.json["result"]["isError"])
		self.assertEqual(frappe.db.get_value("ToDo", self.own, "description"), "MCP write fixture")

	def test_rest_parity(self):
		result = self.result(
			tool="create_document", doctype="ToDo", data={"description": "MCP parity fixture"}
		)
		mcp_name = result["name"]
		response = self.request(
			{"description": "REST parity fixture"}, method="POST", path="/api/v2/document/ToDo"
		)
		self.assertEqual(response.status_code, 200)
		rest_name = response.json["data"]["name"]
		self.names.append(rest_name)
		self.assertEqual(response.json["data"]["owner"], result["owner"])
		result = self.result(tool="update_document", doctype="ToDo", name=mcp_name, data={"status": "Closed"})
		response = self.request({"status": "Closed"}, method="PUT", path=f"/api/v2/document/ToDo/{rest_name}")
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json["data"]["status"], result["status"])
		self.result(tool="delete_document", doctype="ToDo", name=mcp_name)
		response = self.request({}, method="DELETE", path=f"/api/v2/document/ToDo/{rest_name}")
		self.assertEqual(response.status_code, 202)
		self.assertFalse(frappe.db.exists("ToDo", mcp_name))
		self.assertFalse(frappe.db.exists("ToDo", rest_name))

	def test_failed_create_does_not_leave_document(self):
		callback = Mock()

		def after_insert(doc):
			frappe.db.after_commit.add(callback)
			frappe.throw("Create hook failed")

		with patch.object(ToDo, "after_insert", after_insert, create=True):
			response = self.write(
				tool="create_document", doctype="ToDo", data={"description": "MCP failed create fixture"}
			)
		self.assertTrue(response.json["result"]["isError"])
		self.assertFalse(frappe.db.exists("ToDo", {"description": "MCP failed create fixture"}))
		callback.assert_not_called()

	def test_embedded_doctype_cannot_change_create_target(self):
		result = self.result(
			tool="create_document",
			doctype="ToDo",
			data={"doctype": "User", "description": "MCP target fixture"},
		)
		self.assertEqual(result["doctype"], "ToDo")

	def test_custom_name_on_create(self):
		name = f"mcp-write-{self.own}"
		result = self.result(
			tool="create_document", doctype="ToDo", data={"name": name, "description": "MCP named fixture"}
		)
		self.assertEqual(result["name"], name)
