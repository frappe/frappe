# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from unittest.mock import Mock, patch

import frappe
from frappe.mcp import tools
from frappe.mcp.test_utils import McpTestCase

CALLBACK_QUEUES = ("before_commit", "after_commit", "before_rollback", "after_rollback")


class CallbackArguments(tools.ToolArguments):
	pass


class TestToolCallbacks(McpTestCase):
	def invoke(self, handler, prepare=None, inspect=None):
		tool = tools.Tool("callback_test", CallbackArguments, handler)
		original_call = tools.call

		def call(params):
			if prepare:
				prepare()
			result = original_call(params)
			if inspect:
				inspect()
			return result

		with patch("frappe.mcp.tools.registry", return_value=(tool,)), patch("frappe.mcp.tools.call", call):
			return self.request(
				{
					"jsonrpc": "2.0",
					"id": 1,
					"method": "tools/call",
					"params": {"name": "callback_test", "arguments": {}},
				}
			)

	def test_failed_tool_rolls_back_request_callbacks(self):
		events = []
		previous = {name: Mock() for name in CALLBACK_QUEUES}
		current = {name: Mock(side_effect=lambda name=name: events.append(name)) for name in CALLBACK_QUEUES}

		def prepare():
			for name in CALLBACK_QUEUES:
				getattr(frappe.db, name).add(previous[name])

		def handler():
			for name in CALLBACK_QUEUES:
				getattr(frappe.db, name).add(current[name])
			frappe.throw("Callback rollback test")

		response = self.invoke(handler, prepare)
		self.assertTrue(response.json["result"]["isError"])
		self.assertEqual(events, ["before_rollback", "after_rollback"])
		for name in ("before_commit", "after_commit"):
			previous[name].assert_not_called()
			current[name].assert_not_called()
		for name in ("before_rollback", "after_rollback"):
			previous[name].assert_called_once_with()
			current[name].assert_called_once_with()

	def test_successful_tool_keeps_request_callbacks_in_order(self):
		events = []
		original = {}

		def prepare():
			for name in CALLBACK_QUEUES:
				queue = getattr(frappe.db, name)
				queue.add(lambda name=name: events.append(f"earlier_{name}"))
				original[name] = (queue, len(queue))

		def handler():
			for name in CALLBACK_QUEUES:
				getattr(frappe.db, name).add(lambda name=name: events.append(f"tool_{name}"))
			return {"ok": True}

		def inspect():
			for name, (queue, count) in original.items():
				self.assertIs(getattr(frappe.db, name), queue)
				self.assertEqual(len(queue), count + 1)

		response = self.invoke(handler, prepare, inspect)
		self.assertFalse(response.json["result"]["isError"])
		self.assertEqual(
			events,
			["earlier_before_commit", "tool_before_commit", "earlier_after_commit", "tool_after_commit"],
		)

	def test_serialization_failure_discards_commit_callback(self):
		callback = Mock()
		cleanup = Mock()

		def handler():
			frappe.db.after_commit.add(callback)
			frappe.db.after_rollback.add(cleanup)
			return {"value": float("nan")}

		response = self.invoke(handler)
		self.assertTrue(response.json["result"]["isError"])
		callback.assert_not_called()
		cleanup.assert_called_once_with()

	def test_rollback_cleanup_can_register_another_cleanup(self):
		cleanup = Mock()

		def handler():
			frappe.db.before_rollback.add(lambda: frappe.db.after_rollback.add(cleanup))
			frappe.throw("Rollback cleanup test")

		response = self.invoke(handler)
		self.assertTrue(response.json["result"]["isError"])
		cleanup.assert_called_once_with()

	def test_serialization_failure_after_commit_preserves_committed_work(self):
		committed = Mock()
		pending = Mock()
		cleanup = Mock()
		names = []

		def handler():
			doc = frappe.get_doc(doctype="ToDo", description="Committed before serialization").insert()
			names.append(doc.name)
			frappe.db.after_commit.add(committed)
			frappe.db.commit()  # nosemgrep
			doc.description = "Pending before serialization"
			doc.save()
			frappe.db.after_commit.add(pending)
			frappe.db.after_rollback.add(cleanup)
			return {"value": float("nan")}

		try:
			response = self.invoke(handler)
			self.assertTrue(response.json["result"]["isError"])
			self.assertEqual(
				frappe.db.get_value("ToDo", names[0], "description"), "Committed before serialization"
			)
			committed.assert_called_once_with()
			pending.assert_not_called()
			cleanup.assert_called_once_with()
		finally:
			frappe.set_user("Administrator")
			for name in names:
				frappe.delete_doc_if_exists("ToDo", name)
			frappe.db.commit()  # nosemgrep

	def test_commit_during_rollback_cleanup_does_not_mask_tool_error(self):
		def handler():
			frappe.db.before_rollback.add(frappe.db.commit)
			frappe.throw("Tool failed before cleanup")

		response = self.invoke(handler)
		self.assertTrue(response.json["result"]["isError"])
		self.assertEqual(response.json["result"]["content"][0]["text"], "Tool failed before cleanup")

	def test_explicit_boundary_settles_earlier_callbacks(self):
		for operation in ("commit", "rollback"):
			with self.subTest(operation=operation):
				events = []
				original = {}

				def prepare():
					for name in CALLBACK_QUEUES:
						queue = getattr(frappe.db, name)
						queue.add(lambda name=name: events.append(f"earlier_{name}"))
						original[name] = queue

				def handler():
					for name in CALLBACK_QUEUES:
						getattr(frappe.db, name).add(lambda name=name: events.append(f"tool_{name}"))
					getattr(frappe.db, operation)()
					return {"ok": True}

				def inspect():
					for name, queue in original.items():
						self.assertIs(getattr(frappe.db, name), queue)
						self.assertEqual(len(queue), 0)

				response = self.invoke(handler, prepare, inspect)
				self.assertFalse(response.json["result"]["isError"])
				self.assertEqual(
					events,
					[
						f"earlier_before_{operation}",
						f"tool_before_{operation}",
						f"earlier_after_{operation}",
						f"tool_after_{operation}",
					],
				)

	def test_failed_tool_rolls_back_earlier_request_write(self):
		names = []

		def prepare():
			doc = frappe.get_doc(doctype="ToDo", description="Earlier MCP request write").insert()
			names.append(doc.name)

		def handler():
			frappe.throw("Tool failed after earlier write")

		try:
			response = self.invoke(handler, prepare)
			self.assertTrue(response.json["result"]["isError"])
			self.assertFalse(frappe.db.exists("ToDo", names[0]))
		finally:
			frappe.set_user("Administrator")
			for name in names:
				frappe.delete_doc_if_exists("ToDo", name)
			frappe.db.commit()  # nosemgrep
