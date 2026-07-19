# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from frappe import _

from flow.lib.model import ChatResponse, Model, ToolCall, ToolCallBegin
from flow.lib.tool import Tool

if TYPE_CHECKING:
	from flow.knowledge import Knowledge

DEFAULT_MAX_ITERATIONS = 20
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


@dataclass
class TextChunk:
	"""A token delta from the model. Emitted as the LLM streams its reply."""

	text: str


@dataclass
class ToolStarted:
	"""A tool call is about to execute. Lets the UI render a 'thinking' indicator. Emitted as soon
	as the model starts streaming the call, so `arguments` may still be empty at that point — the
	full arguments arrive on the matching ToolEnded."""

	id: str
	name: str
	arguments: dict[str, Any]


@dataclass
class ToolEnded:
	"""A tool call finished. `result` is the JSON-serialized return value."""

	id: str
	name: str
	result: str


@dataclass
class Done:
	"""Terminal event: the run finished (Completed or Paused)."""

	result: RunResult


Event = TextChunk | ToolStarted | ToolEnded | Done


class Agent:
	def __init__(
		self,
		*,
		model: Model | str,
		name: str = "agent",
		instructions: str | None = None,
		tools: list[Tool] | None = None,
		knowledge: Knowledge | list[Knowledge] | None = None,
		max_iterations: int = DEFAULT_MAX_ITERATIONS,
		auto_approve: bool = False,
	):
		if max_iterations < 1:
			raise ValueError("max_iterations must be at least 1")

		# Autonomous runs (triggers) auto-run confirmation tools; nobody is there to approve.
		self.auto_approve = auto_approve
		self.name = name
		self.model = Model(model) if isinstance(model, str) else model
		self.instructions = instructions
		self.tools = list(tools or [])
		if knowledge:
			from flow.tools.builtins import bind_search_knowledge

			items = knowledge if isinstance(knowledge, list) else [knowledge]
			self.tools.append(bind_search_knowledge([k.name for k in items]))
		self.max_iterations = max_iterations

		self._tools_by_name: dict[str, Tool] = {}
		for tool in self.tools:
			if tool.name in self._tools_by_name:
				raise ValueError(f"Duplicate tool name: {tool.name!r}")
			self._tools_by_name[tool.name] = tool

	def run(self, input: str | list[dict[str, Any]], *, stream: bool = False) -> RunResult | Generator[Event]:
		"""Run the agent on `input`. With `stream=True`, returns a generator of `Event`s
		(text deltas, tool start/end markers, and a final `Done` carrying the `RunResult`)."""
		messages = self._build_initial_messages(input)
		if stream:
			return self._loop_stream(messages)
		return self._loop(messages)

	def resume(
		self,
		messages: list[dict[str, Any]],
		answers: dict[str, Any],
		*,
		stream: bool = False,
	) -> RunResult | Generator[Event]:
		"""Continue a run that paused on a question.

		`answers` maps each pending tool_call_id to the user's answer: "Approve" runs
		the tool, "Deny" records the rejection and stops the run, and any other free
		text is returned to the LLM as redirect feedback so it can adjust and retry.
		"""
		if stream:
			return self._resume_stream(messages, answers)
		messages, _ = self._prepare_resume(messages, answers)
		if _has_denial(answers):
			return self._stopped_result(messages)
		return self._loop(messages, self._answered_calls(messages))

	def _resume_stream(self, messages: list[dict[str, Any]], answers: dict[str, Any]) -> Generator[Event]:
		"""Stream a resume: first replay the just-resolved tool results so the UI can fill in
		the tool cards that were awaiting an answer, then continue the agent loop (or stop
		if the user denied)."""
		messages, resolved = self._prepare_resume(messages, answers)
		for call, content in resolved:
			yield ToolEnded(id=call.id, name=call.name, result=content)
		if _has_denial(answers):
			yield Done(result=self._stopped_result(messages))
			return
		yield from self._loop_stream(messages, self._answered_calls(messages))

	def _stopped_result(self, messages: list[dict[str, Any]]) -> RunResult:
		"""Terminal result for a run the user denied: pending calls are already resolved in
		`messages`, so end the turn here without another model call (no further tokens)."""
		return RunResult(
			output=None,
			messages=messages,
			tool_calls=self._answered_calls(messages),
			iterations=0,
		)

	def new_session(self, *, title: str | None = None) -> Any:
		"""Start a persisted conversation driven by this code agent (session's agent link is left empty)."""
		from flow.lib.session import new_session

		return new_session(self, title=title)

	def snapshot(self) -> dict[str, Any]:
		"""Config record stored on each Flow Run for traceability."""
		return {
			"title": self.name,
			"model": self.model.model_id,
			"instructions": self.instructions,
			"tools": [t.name for t in self.tools],
			"max_iterations": self.max_iterations,
		}

	def _prepare_resume(
		self, messages: list[dict[str, Any]], answers: dict[str, Any]
	) -> tuple[list[dict[str, Any]], list[tuple[ToolCall, str]]]:
		"""Append a tool result for each pending call. Returns the new messages plus the
		(call, content) pairs resolved, so a streaming resume can replay them as events."""
		_validate_messages(messages)
		messages = list(messages)
		pending = self._pending_calls(messages)
		if not pending:
			raise ValueError("No questions awaiting an answer in the provided messages")

		resolved: list[tuple[ToolCall, str]] = []
		for call in pending:
			answer = answers.get(call.id)
			tool = self._tools_by_name.get(call.name)
			if tool is not None and tool.requires_confirmation:
				content = self._resolve_confirmation(call, answer)
			else:
				content = _serialize_tool_result(answer)
			messages.append({"role": "tool", "tool_call_id": call.id, "content": content})
			resolved.append((call, content))
		return messages, resolved

	def _resolve_confirmation(self, call: ToolCall, answer: Any) -> str:
		"""Run the tool if approved; deny if rejected; redirect with user feedback otherwise."""
		if answer == "Approve":
			result = self._run_tool(call)
			return _serialize_tool_result(result)
		if answer == "Deny":
			return json.dumps({"status": "denied", "message": "User denied this tool call."})
		# Free-text "Other"
		return json.dumps(
			{
				"status": "redirect",
				"message": "Tool not executed.",
				"user_feedback": answer,
				"instruction": "The user wants changes before this proceeds. Read their feedback carefully, adjust your approach, and try again.",
			}
		)

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

	def _loop_stream(
		self, messages: list[dict[str, Any]], executed_calls: list[ToolCall] | None = None
	) -> Generator[Event]:
		tool_schemas = [t.to_dict() for t in self.tools] or None
		executed_calls = executed_calls if executed_calls is not None else []
		usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

		for iteration in range(1, self.max_iterations + 1):
			chunks = self.model.chat(messages, tools=tool_schemas, stream=True)
			# Tool calls are announced mid-stream (ToolCallBegin) so the UI shows the tool the moment
			# the model starts it, before its arguments finish streaming.
			try:
				while True:
					item = next(chunks)
					if isinstance(item, ToolCallBegin):
						yield ToolStarted(id=item.id, name=item.name, arguments={})
					else:
						yield TextChunk(text=item)
			except StopIteration as e:
				response = e.value
			_accumulate_usage(usage_total, response.usage)
			messages.append(_assistant_message(response))

			if not response.tool_calls:
				yield Done(
					result=RunResult(
						output=response.content,
						messages=messages,
						tool_calls=executed_calls,
						iterations=iteration,
						usage=usage_total,
					)
				)
				return

			questions: list[Question] = []
			for call in response.tool_calls:
				# Re-announce with the full arguments now that they've finished streaming, before the
				# tool runs — so the UI shows the arguments during execution, not only with the result.
				yield ToolStarted(id=call.id, name=call.name, arguments=call.arguments)
				result = self._invoke(call)
				if isinstance(result, Question):
					result.key = call.id
					questions.append(result)
					yield ToolEnded(id=call.id, name=call.name, result="")
					continue

				executed_calls.append(call)
				serialized = _serialize_tool_result(result)
				messages.append({"role": "tool", "tool_call_id": call.id, "content": serialized})
				yield ToolEnded(id=call.id, name=call.name, result=serialized)

			if questions:
				yield Done(
					result=RunResult(
						output=response.content,
						messages=messages,
						tool_calls=executed_calls,
						iterations=iteration,
						usage=usage_total,
						paused=True,
						questions=questions,
					)
				)
				return

		raise RuntimeError(f"Agent {self.name!r} exceeded max_iterations ({self.max_iterations})")

	def _pending_calls(self, messages: list[dict[str, Any]]) -> list[ToolCall]:
		"""Tool calls in the transcript that have no tool result yet (awaiting an answer)."""
		return self._transcript_calls(messages, answered=False)

	def _answered_calls(self, messages: list[dict[str, Any]]) -> list[ToolCall]:
		"""Tool calls in the transcript that already have a tool result (executed)."""
		return self._transcript_calls(messages, answered=True)

	def _transcript_calls(self, messages: list[dict[str, Any]], *, answered: bool) -> list[ToolCall]:
		has_result = {m.get("tool_call_id") for m in messages if m.get("role") == "tool"}
		calls: list[ToolCall] = []
		for message in messages:
			if message.get("role") != "assistant":
				continue
			for tc in message.get("tool_calls") or []:
				if (tc["id"] in has_result) != answered:
					continue
				fn = tc["function"]
				arguments = fn.get("arguments") or "{}"
				calls.append(ToolCall(id=tc["id"], name=fn["name"], arguments=json.loads(arguments)))
		return calls

	def _build_initial_messages(self, input: str | list[dict[str, Any]]) -> list[dict[str, Any]]:
		"""For a string, build [system?, user]. For a list, trust the caller and use it as-is —
		the caller owns the system message and any history."""
		if isinstance(input, str):
			messages: list[dict[str, Any]] = []
			if self.instructions:
				messages.append({"role": "system", "content": self.instructions})
			messages.append({"role": "user", "content": input})
			return messages
		_validate_messages(input)
		return list(input)

	def _invoke(self, call: ToolCall) -> Any:
		"""Run a tool and return its raw result. A Question (returned or synthesized for
		`requires_confirmation` tools) signals a pause."""
		if call.error:
			return json.dumps({"error": call.error})
		tool = self._tools_by_name.get(call.name)
		if tool is None:
			return json.dumps({"error": f"Unknown tool: {call.name!r}"})
		if tool.requires_confirmation and not self.auto_approve:
			return _confirmation_question(call, tool)
		return self._run_tool(call)

	def _run_tool(self, call: ToolCall) -> Any:
		"""Invoke the tool, returning its result or a serialized error message."""
		tool = self._tools_by_name[call.name]
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


def _confirmation_question(call: ToolCall, tool: Tool) -> Question:
	"""Build the approval prompt shown to the user for a `requires_confirmation` tool call.
	Uses the tool's `confirm_prompt` for a plain-English summary, falling back to a JSON dump."""
	if tool.confirm_prompt:
		body = tool.confirm_prompt(call.arguments)
	else:
		body = json.dumps(call.arguments, indent=2, default=str)
	return Question(
		prompt=_("Approve `{0}`?\n\n{1}").format(call.name, body),
		options=["Approve", "Deny"],
		allow_other=True,
	)


def _has_denial(answers: dict[str, Any]) -> bool:
	"""A Deny answer halts the run — the user rejected an action, so stop rather than
	continue. Approve and free-text (redirect) answers let the run proceed."""
	return any(answer == "Deny" for answer in answers.values())


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
