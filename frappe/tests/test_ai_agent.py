# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
from typing import Any

from frappe.ai.agent import Agent, RunResult
from frappe.ai.model import ChatResponse, ToolCall
from frappe.ai.tool import tool
from frappe.tests import UnitTestCase


class FakeModel:
	def __init__(self, responses: list[ChatResponse]):
		self._responses = list(responses)
		self.calls: list[dict[str, Any]] = []

	def chat(self, messages, tools=None):
		self.calls.append({"messages": list(messages), "tools": tools})
		if not self._responses:
			raise AssertionError("FakeModel ran out of scripted responses")
		return self._responses.pop(0)


def _final(text: str, usage: dict[str, int] | None = None) -> ChatResponse:
	return ChatResponse(
		content=text,
		finish_reason="stop",
		usage=usage or {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
	)


def _tool_call(name: str, arguments: dict[str, Any], call_id: str = "call_1") -> ChatResponse:
	return ChatResponse(
		content=None,
		tool_calls=[ToolCall(id=call_id, name=name, arguments=arguments)],
		finish_reason="tool_calls",
		usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
	)


class TestAgentBasics(UnitTestCase):
	def test_run_without_tools_returns_final_output(self):
		model = FakeModel([_final("hello")])
		agent = Agent(model=model)

		result = agent.run("hi")

		self.assertIsInstance(result, RunResult)
		self.assertEqual(result.output, "hello")
		self.assertEqual(result.iterations, 1)
		self.assertEqual(result.tool_calls, [])
		self.assertEqual(result.messages[0], {"role": "user", "content": "hi"})
		self.assertEqual(result.messages[-1]["role"], "assistant")

	def test_instructions_added_as_system_message(self):
		model = FakeModel([_final("ok")])
		agent = Agent(model=model, instructions="You are concise.")

		agent.run("hi")

		first_message = model.calls[0]["messages"][0]
		self.assertEqual(first_message, {"role": "system", "content": "You are concise."})

	def test_run_accepts_message_list_input(self):
		model = FakeModel([_final("ok")])
		agent = Agent(model=model)

		agent.run([{"role": "user", "content": "one"}, {"role": "user", "content": "two"}])

		messages = model.calls[0]["messages"]
		self.assertEqual([m["content"] for m in messages], ["one", "two"])

	def test_usage_is_accumulated_across_iterations(self):
		@tool
		def ping() -> str:
			"""Ping."""
			return "pong"

		model = FakeModel(
			[
				ChatResponse(
					content=None,
					tool_calls=[ToolCall(id="c1", name="ping", arguments={})],
					usage={"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
				),
				_final("done", usage={"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4}),
			]
		)
		agent = Agent(model=model, tools=[ping])

		result = agent.run("hi")

		self.assertEqual(result.usage, {"prompt_tokens": 8, "completion_tokens": 3, "total_tokens": 11})


class TestAgentToolLoop(UnitTestCase):
	def test_executes_tool_call_and_loops_to_final_response(self):
		@tool
		def add(a: int, b: int) -> int:
			"""Add."""
			return a + b

		model = FakeModel([_tool_call("add", {"a": 2, "b": 3}), _final("result is 5")])
		agent = Agent(model=model, tools=[add])

		result = agent.run("add 2 and 3")

		self.assertEqual(result.output, "result is 5")
		self.assertEqual(result.iterations, 2)
		self.assertEqual(len(result.tool_calls), 1)
		self.assertEqual(result.tool_calls[0].name, "add")

		tool_message = next(m for m in result.messages if m["role"] == "tool")
		self.assertEqual(tool_message["tool_call_id"], "call_1")
		self.assertEqual(tool_message["content"], "5")

	def test_tool_schemas_are_passed_to_model(self):
		@tool
		def echo(text: str) -> str:
			"""Echo."""
			return text

		model = FakeModel([_final("ok")])
		agent = Agent(model=model, tools=[echo])

		agent.run("hi")

		passed_tools = model.calls[0]["tools"]
		self.assertEqual(len(passed_tools), 1)
		self.assertEqual(passed_tools[0]["function"]["name"], "echo")

	def test_no_tools_means_tools_param_is_none(self):
		model = FakeModel([_final("ok")])
		agent = Agent(model=model)

		agent.run("hi")

		self.assertIsNone(model.calls[0]["tools"])

	def test_unknown_tool_call_returns_error_to_model(self):
		model = FakeModel([_tool_call("nonexistent", {}), _final("recovered")])
		agent = Agent(model=model)

		result = agent.run("hi")

		tool_message = next(m for m in result.messages if m["role"] == "tool")
		payload = json.loads(tool_message["content"])
		self.assertIn("Unknown tool", payload["error"])
		self.assertEqual(result.output, "recovered")

	def test_tool_exception_is_caught_and_returned_to_model(self):
		@tool
		def boom() -> str:
			"""Raises."""
			raise RuntimeError("kaboom")

		model = FakeModel([_tool_call("boom", {}), _final("handled")])
		agent = Agent(model=model, tools=[boom])

		result = agent.run("hi")

		tool_message = next(m for m in result.messages if m["role"] == "tool")
		payload = json.loads(tool_message["content"])
		self.assertEqual(payload["error"], "kaboom")
		self.assertEqual(result.output, "handled")

	def test_tool_validation_error_is_caught(self):
		@tool
		def add(a: int, b: int) -> int:
			"""Add."""
			return a + b

		model = FakeModel([_tool_call("add", {"a": "not a number", "b": 3}), _final("recovered")])
		agent = Agent(model=model, tools=[add])

		result = agent.run("hi")

		tool_message = next(m for m in result.messages if m["role"] == "tool")
		self.assertIn("error", json.loads(tool_message["content"]))
		self.assertEqual(result.output, "recovered")

	def test_dict_tool_result_is_json_serialized(self):
		@tool
		def lookup(city: str) -> dict:
			"""Lookup."""
			return {"city": city, "temp": 72}

		model = FakeModel([_tool_call("lookup", {"city": "Mumbai"}), _final("ok")])
		agent = Agent(model=model, tools=[lookup])

		result = agent.run("hi")

		tool_message = next(m for m in result.messages if m["role"] == "tool")
		self.assertEqual(json.loads(tool_message["content"]), {"city": "Mumbai", "temp": 72})

	def test_multiple_tool_calls_in_one_response_all_execute(self):
		@tool
		def ping() -> str:
			"""Ping."""
			return "pong"

		model = FakeModel(
			[
				ChatResponse(
					content=None,
					tool_calls=[
						ToolCall(id="c1", name="ping", arguments={}),
						ToolCall(id="c2", name="ping", arguments={}),
					],
				),
				_final("done"),
			]
		)
		agent = Agent(model=model, tools=[ping])

		result = agent.run("hi")

		tool_messages = [m for m in result.messages if m["role"] == "tool"]
		self.assertEqual([m["tool_call_id"] for m in tool_messages], ["c1", "c2"])
		self.assertEqual(len(result.tool_calls), 2)


class TestAgentInputValidation(UnitTestCase):
	def test_non_list_non_str_input_rejected(self):
		agent = Agent(model=FakeModel([]))
		with self.assertRaises(TypeError):
			agent.run(42)

	def test_non_dict_element_rejected(self):
		agent = Agent(model=FakeModel([]))
		with self.assertRaises(TypeError):
			agent.run(["not a dict"])

	def test_missing_role_rejected(self):
		agent = Agent(model=FakeModel([]))
		with self.assertRaises(ValueError) as ctx:
			agent.run([{"content": "hi"}])
		self.assertIn("role", str(ctx.exception))

	def test_invalid_role_rejected(self):
		agent = Agent(model=FakeModel([]))
		with self.assertRaises(ValueError):
			agent.run([{"role": "robot", "content": "hi"}])

	def test_tool_message_without_tool_call_id_rejected(self):
		agent = Agent(model=FakeModel([]))
		with self.assertRaises(ValueError) as ctx:
			agent.run([{"role": "tool", "content": "result"}])
		self.assertIn("tool_call_id", str(ctx.exception))

	def test_message_without_content_or_tool_calls_rejected(self):
		agent = Agent(model=FakeModel([]))
		with self.assertRaises(ValueError):
			agent.run([{"role": "user"}])

	def test_assistant_message_with_only_tool_calls_accepted(self):
		model = FakeModel([_final("ok")])
		agent = Agent(model=model)
		agent.run(
			[
				{
					"role": "assistant",
					"tool_calls": [
						{"id": "c1", "type": "function", "function": {"name": "x", "arguments": "{}"}}
					],
				},
				{"role": "tool", "tool_call_id": "c1", "content": "result"},
			]
		)


class TestAgentLimits(UnitTestCase):
	def test_max_iterations_raises_when_exceeded(self):
		looping = ChatResponse(
			content=None,
			tool_calls=[ToolCall(id="c", name="ping", arguments={})],
		)

		@tool
		def ping() -> str:
			"""Ping."""
			return "pong"

		model = FakeModel([looping, looping, looping])
		agent = Agent(model=model, tools=[ping], max_iterations=2)

		with self.assertRaises(RuntimeError) as ctx:
			agent.run("hi")
		self.assertIn("max_iterations", str(ctx.exception))

	def test_max_iterations_must_be_positive(self):
		with self.assertRaises(ValueError):
			Agent(model=FakeModel([]), max_iterations=0)

	def test_duplicate_tool_names_rejected(self):
		@tool(name="dup")
		def a() -> str:
			"""A."""
			return "a"

		@tool(name="dup")
		def b() -> str:
			"""B."""
			return "b"

		with self.assertRaises(ValueError):
			Agent(model=FakeModel([]), tools=[a, b])
