# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from frappe.ai.model import ChatResponse, Model, ToolCall
from frappe.ai.tool import Tool

DEFAULT_MAX_ITERATIONS = 10
ERROR_MESSAGE_LIMIT = 500
VALID_ROLES = frozenset({"system", "user", "assistant", "tool"})


@dataclass
class Question:
	"""An LLM-authored prompt shown to the user when a run pauses.

	The same shape covers a free-text ask (empty `options`), a single- or
	multi-select. When `allow_other` is true the picker always offers an "Other"
	choice that opens a textbox for the user to reiterate or redirect.
	`key` routes the answer back (e.g. the tool_call_id it belongs to).
	"""

	prompt: str
	options: list[str] = field(default_factory=list)
	multi_select: bool = False
	allow_other: bool = True
	key: str | None = None


@dataclass
class RunResult:
	output: str | None
	messages: list[dict[str, Any]]
	tool_calls: list[ToolCall] = field(default_factory=list)
	iterations: int = 0
	usage: dict[str, int] = field(default_factory=dict)
	paused: bool = False
	questions: list[Question] = field(default_factory=list)


class Agent:
	def __init__(
		self,
		*,
		model: Model | str,
		name: str = "agent",
		instructions: str | None = None,
		tools: list[Tool] | None = None,
		max_iterations: int = DEFAULT_MAX_ITERATIONS,
	):
		if max_iterations < 1:
			raise ValueError("max_iterations must be at least 1")

		self.name = name
		self.model = Model(model) if isinstance(model, str) else model
		self.instructions = instructions
		self.tools = list(tools or [])
		self.max_iterations = max_iterations

		self._tools_by_name: dict[str, Tool] = {}
		for tool in self.tools:
			if tool.name in self._tools_by_name:
				raise ValueError(f"Duplicate tool name: {tool.name!r}")
			self._tools_by_name[tool.name] = tool

	def run(self, input: str | list[dict[str, Any]]) -> RunResult:
		return self._loop(self._build_initial_messages(input))

	def resume(self, messages: list[dict[str, Any]], answers: dict[str, Any]) -> RunResult:
		"""Continue a run that paused on a question.

		`answers` maps each pending tool_call_id to the user's answer (a chosen option,
		a list for multi-select, or free "Other" text). The answer becomes that call's
		result, and the LLM decides what to do next.
		"""
		_validate_messages(messages)
		messages = list(messages)
		pending = self._pending_calls(messages)
		if not pending:
			raise ValueError("No questions awaiting an answer in the provided messages")

		for call in pending:
			content = _serialize_tool_result(answers.get(call.id))
			messages.append({"role": "tool", "tool_call_id": call.id, "content": content})

		return self._loop(messages)

	def _loop(
		self, messages: list[dict[str, Any]], executed_calls: list[ToolCall] | None = None
	) -> RunResult:
		tool_schemas = [t.to_dict() for t in self.tools] or None
		executed_calls = executed_calls if executed_calls is not None else []
		usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

		for iteration in range(1, self.max_iterations + 1):
			response = self.model.chat(messages, tools=tool_schemas)
			_accumulate_usage(usage_total, response.usage)
			messages.append(_assistant_message(response))

			if not response.tool_calls:
				return RunResult(
					output=response.content,
					messages=messages,
					tool_calls=executed_calls,
					iterations=iteration,
					usage=usage_total,
				)

			questions: list[Question] = []
			for call in response.tool_calls:
				result = self._invoke(call)
				if isinstance(result, Question):
					result.key = call.id
					questions.append(result)
					continue

				executed_calls.append(call)
				messages.append(
					{
						"role": "tool",
						"tool_call_id": call.id,
						"content": _serialize_tool_result(result),
					}
				)

			if questions:
				return RunResult(
					output=response.content,
					messages=messages,
					tool_calls=executed_calls,
					iterations=iteration,
					usage=usage_total,
					paused=True,
					questions=questions,
				)

		raise RuntimeError(f"Agent {self.name!r} exceeded max_iterations ({self.max_iterations})")

	def _pending_calls(self, messages: list[dict[str, Any]]) -> list[ToolCall]:
		"""Tool calls in the transcript that have no tool result yet (awaiting an answer)."""
		answered = {m.get("tool_call_id") for m in messages if m.get("role") == "tool"}
		pending: list[ToolCall] = []
		for message in messages:
			if message.get("role") != "assistant":
				continue
			for tc in message.get("tool_calls") or []:
				if tc["id"] in answered:
					continue
				fn = tc["function"]
				arguments = fn.get("arguments") or "{}"
				pending.append(ToolCall(id=tc["id"], name=fn["name"], arguments=json.loads(arguments)))
		return pending

	def _build_initial_messages(self, input: str | list[dict[str, Any]]) -> list[dict[str, Any]]:
		messages: list[dict[str, Any]] = []
		if self.instructions:
			messages.append({"role": "system", "content": self.instructions})
		if isinstance(input, str):
			messages.append({"role": "user", "content": input})
		else:
			_validate_messages(input)
			messages.extend(input)
		return messages

	def _invoke(self, call: ToolCall) -> Any:
		"""Run a tool and return its raw result (a Question signals a pause)."""
		tool = self._tools_by_name.get(call.name)
		if tool is None:
			return json.dumps({"error": f"Unknown tool: {call.name!r}"})
		try:
			return tool(**call.arguments)
		except Exception as e:
			return json.dumps({"error": str(e)[:ERROR_MESSAGE_LIMIT]})


def _validate_messages(messages: Any) -> None:
	if not isinstance(messages, list):
		raise TypeError(f"input must be a str or list of message dicts, got {type(messages).__name__}")
	for i, message in enumerate(messages):
		if not isinstance(message, dict):
			raise TypeError(f"messages[{i}] must be a dict, got {type(message).__name__}")
		role = message.get("role")
		if role not in VALID_ROLES:
			raise ValueError(f"messages[{i}].role must be one of {sorted(VALID_ROLES)}, got {role!r}")
		if role == "tool" and not message.get("tool_call_id"):
			raise ValueError(f"messages[{i}] is a tool message but has no tool_call_id")
		if "content" not in message and "tool_calls" not in message:
			raise ValueError(f"messages[{i}] must have 'content' or 'tool_calls'")


def _assistant_message(response: ChatResponse) -> dict[str, Any]:
	message: dict[str, Any] = {"role": "assistant", "content": response.content}
	if response.tool_calls:
		message["tool_calls"] = [
			{
				"id": call.id,
				"type": "function",
				"function": {
					"name": call.name,
					"arguments": json.dumps(call.arguments),
				},
			}
			for call in response.tool_calls
		]
	return message


def _serialize_tool_result(result: Any) -> str:
	if isinstance(result, str):
		return result
	if result is None:
		return ""
	try:
		return json.dumps(result, default=str)
	except (TypeError, ValueError):
		return str(result)


def _accumulate_usage(total: dict[str, int], delta: dict[str, int]) -> None:
	for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
		total[key] += int(delta.get(key, 0) or 0)
