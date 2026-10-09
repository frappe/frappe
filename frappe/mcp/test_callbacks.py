# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from unittest.mock import Mock, patch

import frappe
from frappe.mcp import tools
from frappe.mcp.test_utils import McpTestCase
from frappe.mcp.transaction import CALLBACK_QUEUES


class CallbackArguments(tools.ToolArguments):
	pass


class TestToolCallbacks(McpTestCase):
	def invoke(self, handler, prepare=None, inspect=None):
		tool = tools.Tool("callback_test", "Callback test", CallbackArguments, handler)
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

	def test_failed_tool_preserves_earlier_callbacks(self):
		events = []
		original = {}
		previous = {name: Mock() for name in CALLBACK_QUEUES}
		current = {name: Mock(side_effect=lambda name=name: events.append(name)) for name in CALLBACK_QUEUES}

		def prepare():
			for name in CALLBACK_QUEUES:
				queue = getattr(frappe.db, name)
				queue.add(previous[name])
				original[name] = (queue, len(queue))

		def handler():
			for name in CALLBACK_QUEUES:
				getattr(frappe.db, name).add(current[name])
			frappe.throw("Callback rollback test")

		def inspect():
			for name, (queue, count) in original.items():
				self.assertIs(getattr(frappe.db, name), queue)
				self.assertEqual(len(queue), count)

		response = self.invoke(handler, prepare, inspect)
		self.assertTrue(response.json["result"]["isError"])
		self.assertEqual(events, ["before_rollback", "after_rollback"])
		for name in ("before_commit", "after_commit"):
			previous[name].assert_called_once_with()
			current[name].assert_not_called()
		for name in ("before_rollback", "after_rollback"):
			previous[name].assert_not_called()
			current[name].assert_called_once_with()

	def test_successful_tool_merges_callbacks_in_order(self):
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

	def test_cleanup_failure_does_not_skip_rollback_or_other_cleanup(self):
		cleanup = Mock()

		def fail():
			raise ValueError("Cleanup failed")

		def handler():
			frappe.get_doc(doctype="ToDo", description="MCP callback cleanup fixture").insert()
			frappe.db.before_rollback.add(fail)
			frappe.db.after_rollback.add(fail)
			frappe.db.after_rollback.add(cleanup)
			frappe.throw("Tool failed")

		with patch("frappe.log_error") as log_error:
			response = self.invoke(handler)
		self.assertTrue(response.json["result"]["isError"])
		self.assertFalse(frappe.db.exists("ToDo", {"description": "MCP callback cleanup fixture"}))
		cleanup.assert_called_once_with()
		self.assertEqual(log_error.call_count, 2)
