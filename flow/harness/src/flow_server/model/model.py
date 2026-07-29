"""The model layer — a provider-neutral interface that turns any LLM's stream into
our typed events.

A `run` call is an async generator: streaming yields `TextDelta` and `ThinkingDelta`
(and a `ToolCallStarted` the moment each tool call's name is known); every turn ends
with a terminal `AssistantMessage` (assembled text + tool calls) followed by a `Usage`.
The loop consumes exactly that contract, whatever the provider underneath.

`LiteLLMModel` is the broad API-key path (any provider litellm supports). Native
providers with their own auth (OAuth/subscription) implement this same interface and
register via the provider registry in `flow_server.model` (see Phase 3).
"""

from __future__ import annotations

import abc
import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, cast

from flow_server.events import (
	AssistantMessage,
	StopReason,
	TextContent,
	TextDelta,
	ThinkingContent,
	ThinkingDelta,
	ToolCall,
	ToolCallStarted,
	ToolResult,
	TranscriptMessage,
	Usage,
	UserMessage,
	_Event,
)
from flow_server.model.errors import normalize_litellm_error


@dataclass(slots=True)
class ModelRequest:
	"""Provider-neutral input for one model turn.

	``cancellation`` is owned by the session. Providers should pass cancellation
	through to their transports where possible; the agent loop also races the model
	iterator against it so a provider that ignores the signal cannot hold a run open.
	"""

	messages: list[TranscriptMessage]
	tools: list[dict[str, Any]] | None = None
	system_prompt: str = "You are a helpful assistant."
	stream: bool = True
	cancellation: asyncio.Event | None = None


class ModelCancelled(Exception):
	"""Internal control flow used when a model request's signal is set."""


async def await_with_cancellation(awaitable: Any, cancellation: asyncio.Event | None) -> Any:
	"""Await one provider operation while making cancellation win any completion race."""
	if cancellation is None:
		return await awaitable

	task = asyncio.ensure_future(awaitable)
	if cancellation.is_set():
		task.cancel()
		with suppress(asyncio.CancelledError):
			await task
		raise ModelCancelled
	cancel_wait = asyncio.create_task(cancellation.wait())
	try:
		done, _ = await asyncio.wait({task, cancel_wait}, return_when=asyncio.FIRST_COMPLETED)
		if cancel_wait in done:
			task.cancel()
			with suppress(asyncio.CancelledError):
				await task
			raise ModelCancelled
		return await task
	except asyncio.CancelledError:
		task.cancel()
		with suppress(asyncio.CancelledError):
			await task
		raise
	finally:
		cancel_wait.cancel()
		with suppress(asyncio.CancelledError):
			await cancel_wait


async def iterate_with_cancellation(
	iterator: AsyncIterator[Any], cancellation: asyncio.Event | None
) -> AsyncIterator[Any]:
	"""Consume and close an async iterator when cancellation is requested."""
	try:
		while True:
			try:
				item = await await_with_cancellation(anext(iterator), cancellation)
			except StopAsyncIteration:
				return
			yield item
	finally:
		aclose = getattr(iterator, "aclose", None)
		if aclose is not None:
			with suppress(Exception):
				await aclose()


class Model(abc.ABC):
	name: str

	@abc.abstractmethod
	def run(self, request: ModelRequest) -> AsyncIterator[_Event]:
		"""Run one model turn over the provider-neutral transcript, yielding typed events.

		Streaming: `TextDelta` per text chunk and one `ToolCallStarted` per tool call.
		Always terminates with an `AssistantMessage` then a `Usage`."""


class LiteLLMModel(Model):
	def __init__(
		self,
		name: str,
		*,
		api_key: str | None = None,
		api_base: str | None = None,
		headers: dict[str, str] | None = None,
		params: dict[str, Any] | None = None,
		api: str = "litellm",
		provider: str | None = None,
		model: str | None = None,
	):
		self.name = name
		self.api = api
		self.provider = provider or (name.split("/", 1)[0] if "/" in name else "litellm")
		self.model = model or name
		self._api_key = api_key
		self._api_base = api_base
		self._headers = headers or {}
		self._params = params or {}

	async def run(self, request: ModelRequest) -> AsyncIterator[_Event]:
		import litellm

		kwargs: dict[str, Any] = {
			"model": self.name,
			"messages": _openai_messages(request.messages, self, request.system_prompt),
			**self._params,
		}
		if self._api_key:
			kwargs["api_key"] = self._api_key
		if self._api_base:
			kwargs["api_base"] = self._api_base
		if self._headers:
			kwargs["extra_headers"] = self._headers
		if request.tools:
			kwargs["tools"] = request.tools
		# Flow owns retries so it can emit one event protocol and keep backoff
		# cancellable. One call to LiteLLM therefore means exactly one provider attempt.
		kwargs["num_retries"] = 0

		if not request.stream:
			try:
				response = await await_with_cancellation(
					litellm.acompletion(**kwargs),
					request.cancellation,
				)
			except ModelCancelled:
				yield self._aborted()
				yield Usage()
				return
			except Exception as exc:
				raise normalize_litellm_error(exc, provider=self.provider) from exc
			choice = (_attr(response, "choices") or [None])[0]
			message = _attr(choice, "message")
			content = _message_content(message)
			yield AssistantMessage(
				content=content,
				api=self.api,
				provider=self.provider,
				model=self.model,
				response_model=_response_model(response, self.name),
				response_id=_attr(response, "id"),
				stop_reason=_stop_reason(
					_attr(choice, "finish_reason"),
					has_tools=any(isinstance(block, ToolCall) for block in content),
				),
			)
			yield _usage_event(_attr(response, "usage"), _cost(response))
			return

		kwargs["stream"] = True
		kwargs["stream_options"] = {"include_usage": True}
		acc: dict[int, dict[str, str]] = {}
		announced: set[int] = set()
		ordered: list[TextContent | ThinkingContent | int] = []
		ordered_tools: set[int] = set()
		thinking_open = False
		usage_obj: Any = None
		cost = 0.0
		finish_reason: str | None = None
		response_id: str | None = None
		response_model: str | None = None

		# `stream=True` lives in kwargs, so litellm's overloads still resolve to the
		# non-streaming ModelResponse; the runtime object is an async chunk iterator.
		try:
			stream_iter = cast(
				AsyncIterator[Any],
				await await_with_cancellation(
					litellm.acompletion(**kwargs),
					request.cancellation,
				),
			)
			async for chunk in iterate_with_cancellation(stream_iter, request.cancellation):
				response_id = response_id or _attr(chunk, "id")
				response_model = response_model or _response_model(chunk, self.name)
				choices = _attr(chunk, "choices") or []
				if choices:
					choice = choices[0]
					delta = _attr(choice, "delta")
					finish_reason = _attr(choice, "finish_reason") or finish_reason
					for part in _reasoning_deltas(delta):
						if part.redacted:
							ordered.append(
								ThinkingContent(
									thinking="",
									thinking_signature=part.signature,
									redacted=True,
								)
							)
							thinking_open = False
							continue
						block = ordered[-1] if thinking_open and ordered else None
						if not isinstance(block, ThinkingContent):
							block = ThinkingContent(thinking="")
							ordered.append(block)
							thinking_open = True
						text = part.text
						if part.signature and text == block.thinking:
							# Anthropic replays the block's accumulated thinking on its
							# signature chunk; Gemini signs a genuinely new fragment.
							text = ""
						if text:
							block.thinking += text
							yield ThinkingDelta(thinking=text)
						if part.signature:
							# A signature seals its block; later reasoning opens a new one.
							block.thinking_signature = part.signature
							thinking_open = False
					text = _attr(delta, "content")
					if text:
						if ordered and isinstance(ordered[-1], TextContent):
							ordered[-1].text += text
						else:
							ordered.append(TextContent(text=text))
						yield TextDelta(text=text)
					for tc in _attr(delta, "tool_calls") or []:
						index = _accumulate_tool_call(acc, tc)
						if index not in ordered_tools:
							ordered_tools.add(index)
							ordered.append(index)
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
		except ModelCancelled:
			finish_reason = "aborted"
		except Exception as exc:
			raise normalize_litellm_error(exc, provider=self.provider) from exc

		calls_by_index = _finalize_tool_call_map(acc)
		content: list[TextContent | ThinkingContent | ToolCall] = []
		for block in ordered:
			if isinstance(block, int):
				call = calls_by_index.get(block)
				if call is not None:
					content.append(call)
			else:
				content.append(block)
		calls = list(calls_by_index.values())
		yield AssistantMessage(
			content=content,
			api=self.api,
			provider=self.provider,
			model=self.model,
			response_model=response_model,
			response_id=response_id,
			stop_reason=(
				"aborted"
				if finish_reason == "aborted"
				else _stop_reason(finish_reason, has_tools=bool(calls))
			),
		)
		yield _usage_event(usage_obj, cost)

	def _aborted(self) -> AssistantMessage:
		return AssistantMessage(
			api=self.api,
			provider=self.provider,
			model=self.model,
			stop_reason="aborted",
		)


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
	return list(_finalize_tool_call_map(acc).values())


def _finalize_tool_call_map(acc: dict[int, dict[str, str]]) -> dict[int, ToolCall]:
	calls: dict[int, ToolCall] = {}
	for index in sorted(acc):
		slot = acc[index]
		if not slot["id"] and not slot["name"]:
			continue
		calls[index] = _build_tool_call(slot["id"], slot["name"], slot["arguments"])
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


def _message_content(message: Any) -> list[TextContent | ThinkingContent | ToolCall]:
	content: list[TextContent | ThinkingContent | ToolCall] = list(_reasoning_blocks(message))
	text = _attr(message, "content")
	if isinstance(text, str) and text:
		content.append(TextContent(text=text))
	content.extend(_message_tool_calls(message))
	return content


def _build_tool_call(call_id: str, name: str, raw_args: str) -> ToolCall:
	"""Parse a tool call's raw JSON arguments. Malformed arguments become a `ToolCall.error`
	the agent feeds back to the model to retry, rather than an exception that fails the run."""
	raw_args = raw_args or ""
	if not raw_args:
		return ToolCall(id=call_id, name=name, arguments={})
	try:
		parsed = json.loads(raw_args)
	except TypeError, ValueError:
		msg = f"Invalid JSON in arguments for {name!r}; resend the call with valid JSON."
		return ToolCall(id=call_id, name=name, arguments={}, error=msg)
	if not isinstance(parsed, dict):
		msg = f"Arguments for {name!r} must be a JSON object."
		return ToolCall(id=call_id, name=name, arguments={}, error=msg)
	return ToolCall(id=call_id, name=name, arguments=parsed)


def _openai_messages(
	messages: list[TranscriptMessage],
	model: LiteLLMModel,
	system_prompt: str,
) -> list[dict[str, Any]]:
	"""Translate canonical transcript messages at the provider boundary."""
	out: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
	for message in messages:
		if isinstance(message, UserMessage):
			out.append({"role": "user", "content": message.content})
		elif isinstance(message, AssistantMessage):
			if message.stop_reason in {"error", "aborted"}:
				continue
			same_model = (
				message.api == model.api
				and message.provider == model.provider
				and message.model == model.model
			)
			text_parts: list[str] = []
			reasoning_parts: list[str] = []
			thinking_blocks: list[dict[str, Any]] = []
			for block in message.content:
				if isinstance(block, TextContent):
					text_parts.append(block.text)
				elif isinstance(block, ThinkingContent):
					if not same_model:
						# deliberately degrades cross-model thinking to ordinary text.
						if block.thinking and not block.redacted:
							text_parts.append(block.thinking)
						continue
					wire = _thinking_block_wire(block)
					if wire is not None:
						thinking_blocks.append(wire)
					if block.thinking and not block.redacted:
						reasoning_parts.append(block.thinking)
			assistant: dict[str, Any] = {
				"role": "assistant",
				"content": "".join(text_parts) or None,
			}
			if message.tool_calls:
				assistant["tool_calls"] = [
					{
						"id": call.id,
						"type": "function",
						"function": {
							"name": call.name,
							"arguments": json.dumps(call.arguments),
						},
					}
					for call in message.tool_calls
				]
			if reasoning_parts:
				assistant["reasoning_content"] = "".join(reasoning_parts)
			# Anthropic-family providers read thinking only from `thinking_blocks`;
			# without them litellm silently drops the `thinking` parameter next turn.
			if thinking_blocks:
				assistant["thinking_blocks"] = thinking_blocks
			out.append(assistant)
		elif isinstance(message, ToolResult):
			out.append(
				{
					"role": "tool",
					"tool_call_id": message.tool_call_id,
					"content": message.content,
				}
			)
	return out


@dataclass(slots=True)
class _ReasoningPart:
	"""One reasoning fragment. A redacted part carries only its opaque payload."""

	text: str = ""
	signature: str | None = None
	redacted: bool = False


def _reasoning_deltas(delta: Any) -> list[_ReasoningPart]:
	"""Reasoning fragments carried by one streamed chunk.

	A fragment's text may be new (Gemini) or a replay of the open block (Anthropic
	restates it alongside the signature); only the caller, which holds the block, can
	tell the two apart."""
	blocks = _attr(delta, "thinking_blocks")
	if isinstance(blocks, list):
		parts = [part for block in blocks if (part := _thinking_block_part(block)) is not None]
		if parts:
			return parts
	text, signature = _reasoning_field(delta)
	return [_ReasoningPart(text=text, signature=signature)] if text else []


def _reasoning_blocks(message: Any) -> list[ThinkingContent]:
	"""Thinking blocks of one non-streamed message, signatures intact."""
	blocks = _attr(message, "thinking_blocks")
	if isinstance(blocks, list):
		content = [
			ThinkingContent(
				thinking=part.text,
				thinking_signature=part.signature,
				redacted=part.redacted,
			)
			for block in blocks
			if (part := _thinking_block_part(block)) is not None
		]
		if content:
			return content
	text, signature = _reasoning_field(message)
	return [ThinkingContent(thinking=text, thinking_signature=signature)] if text else []


def _thinking_block_wire(block: ThinkingContent) -> dict[str, Any] | None:
	"""Anthropic-family replay form. Unsigned thinking cannot be verified upstream, so
	it is left to `reasoning_content` (which the Anthropic path ignores) rather than
	sent as a block the provider would reject."""
	if block.redacted:
		if not block.thinking_signature:
			return None
		return {"type": "redacted_thinking", "data": block.thinking_signature}
	if not block.thinking_signature:
		return None
	return {
		"type": "thinking",
		"thinking": block.thinking,
		"signature": block.thinking_signature,
	}


def _thinking_block_part(block: Any) -> _ReasoningPart | None:
	"""Read one litellm `thinking_blocks` entry (Anthropic-family and Gemini)."""
	if _attr(block, "type") == "redacted_thinking":
		data = _attr(block, "data")
		return _ReasoningPart(signature=data, redacted=True) if isinstance(data, str) and data else None
	text = _attr(block, "thinking")
	signature = _attr(block, "signature")
	part = _ReasoningPart(
		text=text if isinstance(text, str) else "",
		signature=signature if isinstance(signature, str) and signature else None,
	)
	return part if part.text or part.signature else None


def _reasoning_field(value: Any) -> tuple[str, str | None]:
	"""Fallback for providers that expose reasoning as a plain field, not blocks."""
	for key in ("reasoning_content", "reasoning"):
		reasoning = _attr(value, key)
		if isinstance(reasoning, str):
			return reasoning, None
		if isinstance(reasoning, dict):
			text = reasoning.get("content") or reasoning.get("text")
			if isinstance(text, str):
				signature = reasoning.get("signature")
				return text, signature if isinstance(signature, str) else None
	return "", None


def _response_model(value: Any, requested: str) -> str | None:
	actual = _attr(value, "model")
	return actual if isinstance(actual, str) and actual != requested else None


def _stop_reason(value: str | None, *, has_tools: bool = False) -> StopReason:
	"""Map the provider's own signal first; tool calls only upgrade a plain stop.
	A truncated turn must stay "length" so the loop refuses its half-written calls."""
	if value in {"tool_calls", "tool_use"}:
		return "tool_use"
	if value in {"length", "max_tokens", "MAX_TOKENS", "incomplete"}:
		return "length"
	if value in {"abort", "aborted", "cancelled", "canceled"}:
		return "aborted"
	if value in {"error", "content_filter", "network_error"}:
		return "error"
	return "tool_use" if has_tools else "stop"


def _usage_event(usage_obj: Any, cost: float) -> Usage:
	return Usage(
		input_tokens=_attr(usage_obj, "prompt_tokens", 0) or 0,
		output_tokens=_attr(usage_obj, "completion_tokens", 0) or 0,
		cost=cost or 0.0,
	)


def _cost(response: Any) -> float:
	return (getattr(response, "_hidden_params", None) or {}).get("response_cost") or 0.0
