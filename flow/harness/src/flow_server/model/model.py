"""The model layer — a provider-neutral interface that turns any LLM's stream into
our typed events.

A `run` call is an async generator: streaming yields `TextDelta` (and a
`ToolCallStarted` the moment each tool call's name is known); every turn ends with a
terminal `AssistantMessage` (assembled text + tool calls) followed by a `Usage`. The
loop consumes exactly that contract, whatever the provider underneath.

`LiteLLMModel` is the broad API-key path (any provider litellm supports). Native
providers with their own auth (OAuth/subscription) implement this same interface and
register via the provider registry in `flow_server.model` (see Phase 3).
"""

from __future__ import annotations

import abc
import json
from collections.abc import AsyncIterator
from typing import Any

from flow_server.events import AssistantMessage, TextDelta, ToolCall, ToolCallStarted, Usage, _Event


class Model(abc.ABC):
	name: str

	@abc.abstractmethod
	def run(
		self,
		messages: list[dict[str, Any]],
		tools: list[dict[str, Any]] | None = None,
		*,
		stream: bool = True,
	) -> AsyncIterator[_Event]:
		"""Run one model turn over the OpenAI-format `messages`, yielding typed events.

		Streaming: `TextDelta` per text chunk and one `ToolCallStarted` per tool call.
		Always terminates with an `AssistantMessage` then a `Usage`."""


class LiteLLMModel(Model):
	def __init__(
		self,
		name: str,
		*,
		api_key: str | None = None,
		api_base: str | None = None,
		params: dict[str, Any] | None = None,
	):
		self.name = name
		self._api_key = api_key
		self._api_base = api_base
		self._params = params or {}

	async def run(
		self,
		messages: list[dict[str, Any]],
		tools: list[dict[str, Any]] | None = None,
		*,
		stream: bool = True,
	) -> AsyncIterator[_Event]:
		import litellm

		kwargs: dict[str, Any] = {"model": self.name, "messages": messages, **self._params}
		if self._api_key:
			kwargs["api_key"] = self._api_key
		if self._api_base:
			kwargs["api_base"] = self._api_base
		if tools:
			kwargs["tools"] = tools

		if not stream:
			response = await litellm.acompletion(**kwargs)
			choice = (_attr(response, "choices") or [None])[0]
			message = _attr(choice, "message")
			yield AssistantMessage(
				text=_attr(message, "content") or "",
				tool_calls=_message_tool_calls(message),
			)
			yield _usage_event(_attr(response, "usage"), _cost(response))
			return

		kwargs["stream"] = True
		kwargs["stream_options"] = {"include_usage": True}
		acc: dict[int, dict[str, str]] = {}
		announced: set[int] = set()
		parts: list[str] = []
		usage_obj: Any = None
		cost = 0.0

		stream_iter = await litellm.acompletion(**kwargs)
		async for chunk in stream_iter:
			choices = _attr(chunk, "choices") or []
			if choices:
				delta = _attr(choices[0], "delta")
				text = _attr(delta, "content")
				if text:
					parts.append(text)
					yield TextDelta(text=text)
				for tc in _attr(delta, "tool_calls") or []:
					index = _accumulate_tool_call(acc, tc)
					slot = acc[index]
					if index not in announced and slot["id"] and slot["name"]:
						announced.add(index)
						yield ToolCallStarted(id=slot["id"], name=slot["name"])
			chunk_usage = _attr(chunk, "usage")
			if chunk_usage is not None:
				usage_obj = chunk_usage
			chunk_cost = (getattr(chunk, "_hidden_params", None) or {}).get("response_cost")
			if chunk_cost is not None:
				cost = chunk_cost

		yield AssistantMessage(text="".join(parts), tool_calls=_finalize_tool_calls(acc))
		yield _usage_event(usage_obj, cost)


# --- litellm response helpers ---------------------------------------------

def _attr(obj: Any, key: str, default: Any = None) -> Any:
	"""Read a field whether the litellm object exposes it as an attribute or a dict."""
	if obj is None:
		return default
	if isinstance(obj, dict):
		return obj.get(key, default)
	return getattr(obj, key, default)


def _accumulate_tool_call(acc: dict[int, dict[str, str]], delta: Any) -> int:
	"""Fold one streamed tool-call delta into the per-index accumulator."""
	index = _attr(delta, "index", 0) or 0
	slot = acc.setdefault(index, {"id": "", "name": "", "arguments": ""})
	call_id = _attr(delta, "id")
	if call_id:
		slot["id"] = call_id
	function = _attr(delta, "function")
	if function is not None:
		name = _attr(function, "name")
		if name:
			slot["name"] = name
		args = _attr(function, "arguments")
		if args:
			slot["arguments"] += args
	return index


def _finalize_tool_calls(acc: dict[int, dict[str, str]]) -> list[ToolCall]:
	calls: list[ToolCall] = []
	for index in sorted(acc):
		slot = acc[index]
		if not slot["id"] and not slot["name"]:
			continue
		calls.append(_build_tool_call(slot["id"], slot["name"], slot["arguments"]))
	return calls


def _message_tool_calls(message: Any) -> list[ToolCall]:
	calls: list[ToolCall] = []
	for raw in _attr(message, "tool_calls") or []:
		fn = _attr(raw, "function")
		calls.append(
			_build_tool_call(
				_attr(raw, "id", "") or "",
				_attr(fn, "name", "") or "",
				_attr(fn, "arguments", "") or "",
			)
		)
	return calls


def _build_tool_call(call_id: str, name: str, raw_args: str) -> ToolCall:
	"""Parse a tool call's raw JSON arguments. Malformed arguments become a `ToolCall.error`
	the agent feeds back to the model to retry, rather than an exception that fails the run."""
	raw_args = raw_args or ""
	if not raw_args:
		return ToolCall(id=call_id, name=name, args={})
	try:
		parsed = json.loads(raw_args)
	except (TypeError, ValueError):
		msg = f"Invalid JSON in arguments for {name!r}; resend the call with valid JSON."
		return ToolCall(id=call_id, name=name, args={}, error=msg)
	if not isinstance(parsed, dict):
		msg = f"Arguments for {name!r} must be a JSON object."
		return ToolCall(id=call_id, name=name, args={}, error=msg)
	return ToolCall(id=call_id, name=name, args=parsed)


def _usage_event(usage_obj: Any, cost: float) -> Usage:
	return Usage(
		input_tokens=_attr(usage_obj, "prompt_tokens", 0) or 0,
		output_tokens=_attr(usage_obj, "completion_tokens", 0) or 0,
		cost=cost or 0.0,
	)


def _cost(response: Any) -> float:
	return (getattr(response, "_hidden_params", None) or {}).get("response_cost") or 0.0
