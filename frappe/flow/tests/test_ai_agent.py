# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
from typing import Any

from frappe.tests import UnitTestCase

from flow.lib.agent import (
	Agent,
	Done,
	Question,
	RunResult,
	TextChunk,
	ToolEnded,
	ToolStarted,
)
from flow.lib.model import ChatResponse, ToolCall
from flow.lib.tool import tool


class FakeModel:
	def __init__(self, responses: list[ChatResponse], streams: list[list[str]] | None = None):
		"""`responses` are returned by chat(); `streams` (optional) are the text-delta
		sequences yielded when stream=True, one list per call, indexed alongside responses."""
		self._responses = list(responses)
		self._streams = list(streams) if streams is not None else [[r.content or ""] for r in responses]
		self.calls: list[dict[str, Any]] = []

	def chat(self, messages, tools=None, *, stream=False):
		self.calls.append({"messages": list(messages), "tools": tools, "stream": stream})
		if not self._responses:
			raise AssertionError("FakeModel ran out of scripted responses")
		response = self._responses.pop(0)
		text_parts = self._streams.pop(0) if self._streams else [response.content or ""]
		if stream:
			return _scripted_stream(text_parts, response)
		return response


def _scripted_stream(text_parts: list[str], response: ChatResponse):
	for part in text_parts:
		if part:
			yield part
	return response


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


def _ask(prompt: str, options: list[str] | None = None, multi_select: bool = False) -> Question:
	return Question(prompt=prompt, options=options or [], multi_select=multi_select)


class TestAgentConsultation(UnitTestCase):
	def test_question_returning_tool_pauses(self):
		@tool
		def ask_user(prompt: str) -> Question:
			"""Ask the user."""
			return _ask(prompt, options=["Customers", "Leads"])

		model = FakeModel([_tool_call("ask_user", {"prompt": "Which list?"}, call_id="c1")])
		agent = Agent(model=model, tools=[ask_user])

		result = agent.run("email the list")

		self.assertTrue(result.paused)
		self.assertEqual(len(result.questions), 1)
		question = result.questions[0]
		self.assertEqual(question.prompt, "Which list?")
		self.assertEqual(question.options, ["Customers", "Leads"])
		self.assertEqual(question.key, "c1")
		self.assertFalse([m for m in result.messages if m["role"] == "tool"])

	def test_non_question_tools_still_loop(self):
		@tool
		def ping() -> str:
			"""Ping."""
			return "pong"

		model = FakeModel([_tool_call("ping", {}), _final("done")])
		agent = Agent(model=model, tools=[ping])

		result = agent.run("hi")

		self.assertFalse(result.paused)
		self.assertEqual(result.iterations, 2)

	def test_resume_feeds_answer_back_as_result(self):
		@tool
		def ask_user(prompt: str) -> Question:
			"""Ask the user."""
			return _ask(prompt, options=["Customers", "Leads"])

		agent = Agent(
			model=FakeModel([_tool_call("ask_user", {"prompt": "Which list?"}, call_id="c1")]),
			tools=[ask_user],
		)
		paused = agent.run("email the list")

		agent.model = FakeModel([_final("emailed the customers")])
		result = agent.resume(paused.messages, {"c1": "Customers"})

		self.assertFalse(result.paused)
		self.assertEqual(result.output, "emailed the customers")
		tool_msg = next(m for m in result.messages if m["role"] == "tool")
		self.assertEqual(tool_msg["tool_call_id"], "c1")
		self.assertEqual(tool_msg["content"], "Customers")

	def test_resume_serializes_multiselect_answer(self):
		@tool
		def ask_user(prompt: str) -> Question:
			"""Ask the user."""
			return _ask(prompt, options=["A", "B", "C"], multi_select=True)

		agent = Agent(
			model=FakeModel([_tool_call("ask_user", {"prompt": "Which?"}, call_id="c1")]),
			tools=[ask_user],
		)
		paused = agent.run("pick")

		agent.model = FakeModel([_final("ok")])
		result = agent.resume(paused.messages, {"c1": ["A", "C"]})

		tool_msg = next(m for m in result.messages if m["role"] == "tool")
		self.assertEqual(json.loads(tool_msg["content"]), ["A", "C"])

	def test_other_tools_run_while_a_question_pauses(self):
		@tool
		def safe() -> str:
			"""Safe."""
			return "safe-result"

		@tool
		def ask_user(prompt: str) -> Question:
			"""Ask the user."""
			return _ask(prompt)

		response = ChatResponse(
			content=None,
			tool_calls=[
				ToolCall(id="c1", name="safe", arguments={}),
				ToolCall(id="c2", name="ask_user", arguments={"prompt": "ok?"}),
			],
		)
		agent = Agent(model=FakeModel([response]), tools=[safe, ask_user])

		result = agent.run("do both")

		self.assertTrue(result.paused)
		self.assertEqual([c.name for c in result.tool_calls], ["safe"])
		self.assertEqual([q.key for q in result.questions], ["c2"])
		tool_msgs = [m for m in result.messages if m["role"] == "tool"]
		self.assertEqual(len(tool_msgs), 1)
		self.assertEqual(tool_msgs[0]["content"], "safe-result")

	def test_resume_without_pending_raises(self):
		agent = Agent(model=FakeModel([]))
		with self.assertRaises(ValueError):
			agent.resume([{"role": "user", "content": "hi"}], {})


class TestAgentStreaming(UnitTestCase):
	def test_run_stream_yields_text_chunks_then_done(self):
		model = FakeModel([_final("hello world")], streams=[["hello ", "world"]])
		agent = Agent(model=model)

		events = list(agent.run("hi", stream=True))

		texts = [e.text for e in events if isinstance(e, TextChunk)]
		self.assertEqual(texts, ["hello ", "world"])

		done = events[-1]
		self.assertIsInstance(done, Done)
		self.assertIsInstance(done.result, RunResult)
		self.assertEqual(done.result.output, "hello world")
		self.assertEqual(done.result.iterations, 1)
		self.assertFalse(done.result.paused)

	def test_run_stream_passes_stream_flag_to_model(self):
		model = FakeModel([_final("ok")])
		agent = Agent(model=model)

		list(agent.run("hi", stream=True))

		self.assertTrue(model.calls[0]["stream"])

	def test_run_stream_emits_tool_started_and_ended_around_invocation(self):
		@tool
		def add(a: int, b: int) -> int:
			"""Add."""
			return a + b

		model = FakeModel(
			[_tool_call("add", {"a": 2, "b": 3}), _final("five")],
			streams=[[""], ["five"]],
		)
		agent = Agent(model=model, tools=[add])

		events = list(agent.run("add 2 and 3", stream=True))

		started = [e for e in events if isinstance(e, ToolStarted)]
		ended = [e for e in events if isinstance(e, ToolEnded)]
		self.assertEqual(len(started), 1)
		self.assertEqual(started[0].name, "add")
		self.assertEqual(started[0].arguments, {"a": 2, "b": 3})
		self.assertEqual(ended[0].result, "5")

		done = events[-1]
		self.assertIsInstance(done, Done)
		self.assertEqual(done.result.output, "five")
		self.assertEqual(done.result.iterations, 2)

	def test_run_stream_paused_ends_with_done_paused(self):
		@tool
		def ask_user(prompt: str) -> Question:
			"""Ask."""
			return Question(prompt=prompt, options=["A", "B"])

		model = FakeModel([_tool_call("ask_user", {"prompt": "Which?"}, call_id="c1")])
		agent = Agent(model=model, tools=[ask_user])

		events = list(agent.run("pick", stream=True))

		done = events[-1]
		self.assertIsInstance(done, Done)
		self.assertTrue(done.result.paused)
		self.assertEqual(done.result.questions[0].key, "c1")

	def test_run_stream_accumulates_usage_across_iterations(self):
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

		events = list(agent.run("hi", stream=True))

		done = events[-1]
		self.assertEqual(done.result.usage, {"prompt_tokens": 8, "completion_tokens": 3, "total_tokens": 11})

	def test_run_stream_resume_continues_with_answer(self):
		@tool
		def ask_user(prompt: str) -> Question:
			"""Ask."""
			return Question(prompt=prompt, options=["A", "B"])

		agent = Agent(
			model=FakeModel([_tool_call("ask_user", {"prompt": "Which?"}, call_id="c1")]),
			tools=[ask_user],
		)
		paused_events = list(agent.run("pick", stream=True))
		paused = paused_events[-1].result

		agent.model = FakeModel([_final("picked A")], streams=[["picked A"]])
		resumed_events = list(agent.resume(paused.messages, {"c1": "A"}, stream=True))

		texts = [e.text for e in resumed_events if isinstance(e, TextChunk)]
		self.assertEqual("".join(texts), "picked A")
		done = resumed_events[-1]
		self.assertIsInstance(done, Done)
		self.assertEqual(done.result.output, "picked A")

	def test_run_stream_resume_preserves_prior_tool_calls(self):
		@tool
		def lookup() -> str:
			"""Lookup."""
			return "result"

		@tool
		def ask_user(prompt: str) -> Question:
			"""Ask."""
			return Question(prompt=prompt, options=["A", "B"])

		agent = Agent(
			model=FakeModel(
				[
					_tool_call("lookup", {}, call_id="c1"),
					_tool_call("ask_user", {"prompt": "Which?"}, call_id="c2"),
				]
			),
			tools=[lookup, ask_user],
		)
		paused = list(agent.run("look then ask", stream=True))[-1].result
		self.assertEqual([c.name for c in paused.tool_calls], ["lookup"])

		agent.model = FakeModel([_final("done")], streams=[["done"]])
		done = list(agent.resume(paused.messages, {"c2": "A"}, stream=True))[-1]

		self.assertEqual([c.name for c in done.result.tool_calls], ["lookup", "ask_user"])


class TestAgentConfirmation(UnitTestCase):
	def _danger_tool(self):
		calls: list[dict[str, Any]] = []

		@tool(requires_confirmation=True)
		def write_file(path: str, body: str) -> str:
			"""Write text to a file."""
			calls.append({"path": path, "body": body})
			return f"wrote {len(body)} bytes to {path}"

		return write_file, calls

	def test_confirmation_required_tool_pauses_run_without_executing(self):
		write_file, calls = self._danger_tool()
		model = FakeModel([_tool_call("write_file", {"path": "/tmp/x", "body": "hi"}, call_id="c1")])
		agent = Agent(model=model, tools=[write_file])

		result = agent.run("write hi to /tmp/x")

		self.assertTrue(result.paused)
		self.assertEqual(len(result.questions), 1)
		self.assertEqual(result.questions[0].options, ["Approve", "Deny"])
		self.assertTrue(result.questions[0].allow_other)
		self.assertIn("write_file", result.questions[0].prompt)
		self.assertEqual(calls, [])  # tool never ran

	def test_auto_approve_runs_confirmation_tool_without_pausing(self):
		write_file, calls = self._danger_tool()
		model = FakeModel(
			[_tool_call("write_file", {"path": "/tmp/x", "body": "hi"}, call_id="c1"), _final("done")]
		)
		agent = Agent(model=model, tools=[write_file], auto_approve=True)

		result = agent.run("write hi to /tmp/x")

		self.assertFalse(result.paused)
		self.assertEqual(calls, [{"path": "/tmp/x", "body": "hi"}])  # ran unattended
		self.assertEqual(result.output, "done")

	def test_approve_invokes_tool_and_feeds_real_result_to_llm(self):
		write_file, calls = self._danger_tool()
		pause_response = _tool_call("write_file", {"path": "/tmp/x", "body": "hi"}, call_id="c1")
		final_response = _final("done")
		model = FakeModel([pause_response, final_response])
		agent = Agent(model=model, tools=[write_file])

		paused = agent.run("write hi to /tmp/x")
		resumed = agent.resume(paused.messages, {"c1": "Approve"})

		self.assertEqual(calls, [{"path": "/tmp/x", "body": "hi"}])
		tool_message = next(m for m in resumed.messages if m["role"] == "tool")
		self.assertEqual(tool_message["content"], "wrote 2 bytes to /tmp/x")
		self.assertEqual(resumed.output, "done")

	def test_deny_records_rejection_and_stops_without_calling_model(self):
		write_file, calls = self._danger_tool()
		# Only the pausing response is scripted: if resume called the model again,
		# FakeModel would raise "ran out of scripted responses".
		model = FakeModel([_tool_call("write_file", {"path": "/tmp/x", "body": "hi"}, call_id="c1")])
		agent = Agent(model=model, tools=[write_file])

		paused = agent.run("write hi to /tmp/x")
		resumed = agent.resume(paused.messages, {"c1": "Deny"})

		self.assertEqual(calls, [])  # tool never ran
		self.assertFalse(resumed.paused)  # run ended, not paused
		self.assertIsNone(resumed.output)
		self.assertEqual(len(model.calls), 1)  # model not called again after Deny
		tool_message = next(m for m in resumed.messages if m["role"] == "tool")
		self.assertEqual(
			json.loads(tool_message["content"]),
			{"status": "denied", "message": "User denied this tool call."},
		)

	def test_stream_deny_stops_and_replays_denied_call(self):
		write_file, calls = self._danger_tool()
		model = FakeModel([_tool_call("write_file", {"path": "/tmp/x", "body": "hi"}, call_id="c1")])
		agent = Agent(model=model, tools=[write_file])

		paused = agent.run("write hi to /tmp/x")
		events = list(agent.resume(paused.messages, {"c1": "Deny"}, stream=True))

		self.assertEqual(calls, [])  # tool never ran
		self.assertEqual(len(model.calls), 1)  # model not called again after Deny
		# the denied call is replayed as a ToolEnded so the UI can fill its card, then Done
		tool_ended = [e for e in events if isinstance(e, ToolEnded)]
		self.assertEqual(len(tool_ended), 1)
		self.assertEqual(json.loads(tool_ended[0].result)["status"], "denied")
		self.assertIsInstance(events[-1], Done)
		self.assertFalse(events[-1].result.paused)

	def test_confirm_prompt_renders_plain_english_body(self):
		@tool(
			requires_confirmation=True,
			confirm_prompt=lambda args: f"Send email to {args['to']}",
		)
		def send_email(to: str, body: str) -> str:
			"""Send an email."""
			return "sent"

		model = FakeModel([_tool_call("send_email", {"to": "alice@example.com", "body": "hi"}, call_id="c1")])
		agent = Agent(model=model, tools=[send_email])

		result = agent.run("email alice")

		self.assertIn("Send email to alice@example.com", result.questions[0].prompt)
		self.assertNotIn("body", result.questions[0].prompt)  # raw JSON shape isn't leaking through

	def test_free_text_answer_redirects_to_llm_with_feedback(self):
		write_file, calls = self._danger_tool()
		model = FakeModel(
			[
				_tool_call("write_file", {"path": "/tmp/x", "body": "hi"}, call_id="c1"),
				_final("ok"),
			]
		)
		agent = Agent(model=model, tools=[write_file])

		paused = agent.run("write hi")
		resumed = agent.resume(paused.messages, {"c1": "use /tmp/y instead"})

		self.assertEqual(calls, [])  # tool never ran
		tool_message = next(m for m in resumed.messages if m["role"] == "tool")
		payload = json.loads(tool_message["content"])
		self.assertEqual(payload["status"], "redirect")
		self.assertEqual(payload["user_feedback"], "use /tmp/y instead")

	def test_resume_preserves_tool_calls_from_before_the_pause(self):
		write_file, calls = self._danger_tool()

		@tool
		def read_file(path: str) -> str:
			"""Read a file."""
			return "contents"

		model = FakeModel(
			[
				_tool_call("read_file", {"path": "/tmp/a"}, call_id="c1"),
				_tool_call("write_file", {"path": "/tmp/x", "body": "hi"}, call_id="c2"),
			]
		)
		agent = Agent(model=model, tools=[read_file, write_file])

		paused = agent.run("read then write")
		self.assertEqual([c.name for c in paused.tool_calls], ["read_file"])

		agent.model = FakeModel([_final("done")])
		resumed = agent.resume(paused.messages, {"c2": "Approve"})

		self.assertEqual(calls, [{"path": "/tmp/x", "body": "hi"}])  # confirmation ran
		# Both the pre-pause call and the just-approved call survive on the resumed result.
		self.assertEqual([c.name for c in resumed.tool_calls], ["read_file", "write_file"])


class TestQuestion(UnitTestCase):
	def test_defaults_are_open_text_with_other(self):
		q = Question(prompt="What subject line?")
		self.assertEqual(q.options, [])
		self.assertFalse(q.multi_select)
		self.assertTrue(q.allow_other)

	def test_holds_llm_authored_options(self):
		q = Question(
			prompt="I'll delete 5 inactive customers.",
			options=["Go ahead", "Only the 2 oldest"],
			multi_select=False,
			key="c1",
		)
		self.assertEqual(q.options, ["Go ahead", "Only the 2 oldest"])
		self.assertTrue(q.allow_other)
		self.assertEqual(q.key, "c1")


class TestToolCallParsing(UnitTestCase):
	def test_invalid_json_becomes_error_not_raise(self):
		from flow.lib.model import _build_tool_call

		call = _build_tool_call("c1", "read", "{not json")
		self.assertEqual(call.arguments, {})
		self.assertIn("Invalid JSON", call.error)

	def test_non_object_json_is_error(self):
		from flow.lib.model import _build_tool_call

		call = _build_tool_call("c1", "read", "[1, 2]")
		self.assertIn("must be a JSON object", call.error)

	def test_valid_json_parses_without_error(self):
		from flow.lib.model import _build_tool_call

		call = _build_tool_call("c1", "read", '{"doctype": "User"}')
		self.assertIsNone(call.error)
		self.assertEqual(call.arguments, {"doctype": "User"})


class TestAgentMalformedToolCall(UnitTestCase):
	def test_parse_error_feeds_back_and_run_continues(self):
		bad = ChatResponse(
			content=None,
			tool_calls=[
				ToolCall(id="c1", name="read", arguments={}, error="Invalid JSON in arguments for 'read'.")
			],
		)
		model = FakeModel([bad, _final("recovered")])
		agent = Agent(model=model)

		result = agent.run("read something")

		self.assertFalse(result.paused)
		self.assertEqual(result.output, "recovered")
		tool_msg = next(m for m in result.messages if m["role"] == "tool")
		self.assertIn("Invalid JSON", json.loads(tool_msg["content"])["error"])
