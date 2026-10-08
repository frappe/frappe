"""The broad API-key path: any provider LiteLLM can reach, adapted to Flow's events.

`_openai_messages` translates the neutral transcript into OpenAI chat-completions shape
at the provider boundary; `_ResponseAssembler` puts one streamed response back into
ordered content blocks. Thinking blocks survive the round trip with their signatures,
and are degraded to plain text when replayed to a different model.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, cast

from flow_harness.events import (
	AnyEvent,
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
)
from flow_harness.model.base import Model, ModelRequest
from flow_harness.model.cancellation import ModelCancelled, await_with_cancellation, iterate_with_cancellation
from flow_harness.model.catalog import model_supports_images
from flow_harness.model.content import ResolvedImage, resolve_tool_images, resolve_user_content
from flow_harness.model.errors import normalize_litellm_error
from flow_harness.model.retry import run_with_retries
from flow_harness.model.tool_display import tool_call_display_ready_event, with_tool_call_displays


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
		supports_images: bool | None = None,
	):
		self.name = name
		self.api = api
		self.provider = provider or (name.split("/", 1)[0] if "/" in name else "litellm")
		self.model = model or name
		self._api_key = api_key
		self._api_base = api_base
		self._headers = headers or {}
		self._params = params or {}
		self._limits: tuple[int | None, int | None] | None = None
		self._supports_images: bool | None = supports_images

	@property
	def supports_images(self) -> bool | None:
		if self._supports_images is not None:
			return self._supports_images
		return model_supports_images(self.model)

	@property
	def context_window(self) -> int | None:
		return self._model_limits()[0]

	@property
	def max_output_tokens(self) -> int | None:
		return self._model_limits()[1]

	def _model_limits(self) -> tuple[int | None, int | None]:
		if self._limits is None:
			self._limits = litellm_limits(self.name)
		return self._limits

	async def run(self, request: ModelRequest) -> AsyncIterator[AnyEvent]:
		kwargs = self._completion_kwargs(request)

		def start_attempt() -> AsyncIterator[AnyEvent]:
			if request.stream:
				return self._stream_response(
					dict(kwargs), request.cancellation, request.tool_display_templates
				)
			return self._response(dict(kwargs), request.cancellation, request.tool_display_templates)

		try:
			async for event in run_with_retries(
				start_attempt,
				cancellation=request.cancellation,
				provider=self.provider,
			):
				yield event
		except ModelCancelled:
			yield self.aborted_message()
			yield Usage()

	def _completion_kwargs(self, request: ModelRequest) -> dict[str, Any]:
		caching = _uses_explicit_prompt_caching(self.name)
		messages = _openai_messages(
			request.messages,
			self,
			request.system_prompt,
			resolve_attachment=request.resolve_attachment,
		)
		if caching:
			_mark_cache_breakpoints(messages)
		kwargs: dict[str, Any] = {
			"model": self.name,
			"messages": messages,
			**self._params,
			**(request.params or {}),
		}
		if self._api_key:
			kwargs["api_key"] = self._api_key
		if self._api_base:
			kwargs["api_base"] = self._api_base
		if self._headers:
			kwargs["extra_headers"] = self._headers
		if request.tools:
			kwargs["tools"] = _cache_last_tool(request.tools) if caching else request.tools
		if request.max_output_tokens is not None:
			kwargs["max_tokens"] = request.max_output_tokens
		# Flow owns retries so it can emit one event protocol and keep backoff
		# cancellable. One call to LiteLLM therefore means exactly one provider attempt.
		kwargs["num_retries"] = 0
		return kwargs

	async def _response(
		self,
		kwargs: dict[str, Any],
		cancellation: asyncio.Event | None,
		tool_display_templates: Mapping[str, str],
	) -> AsyncIterator[AnyEvent]:
		import litellm

		try:
			response = await await_with_cancellation(litellm.acompletion(**kwargs), cancellation)
		except ModelCancelled:
			raise
		except Exception as exc:
			raise normalize_litellm_error(exc, provider=self.provider) from exc
		choice = (_attr(response, "choices") or [None])[0]
		message = _attr(choice, "message")
		content = _message_content(message)
		result = AssistantMessage(
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
		yield with_tool_call_displays(result, tool_display_templates)
		yield _usage_event(_attr(response, "usage"), _cost(response))

	async def _stream_response(
		self,
		kwargs: dict[str, Any],
		cancellation: asyncio.Event | None,
		tool_display_templates: Mapping[str, str],
	) -> AsyncIterator[AnyEvent]:
		import litellm

		kwargs["stream"] = True
		kwargs["stream_options"] = {"include_usage": True}
		assembler = _ResponseAssembler(tool_display_templates=tool_display_templates)
		try:
			# acompletion returns `ModelResponse | CustomStreamWrapper` and picks at
			# runtime from the `stream` value, which is inside our kwargs dict — so the
			# checker cannot know this call takes the iterator branch. The await itself
			# only opens the response; chunks come from iterating it.
			stream = cast(
				AsyncIterator[Any],
				await await_with_cancellation(litellm.acompletion(**kwargs), cancellation),
			)
			async for chunk in iterate_with_cancellation(stream, cancellation):
				for event in assembler.add_chunk(chunk):
					yield event
		except ModelCancelled:
			assembler.finish_reason = "aborted"  # keep any partial content in the terminal
		except Exception as exc:
			raise normalize_litellm_error(exc, provider=self.provider) from exc

		yield assembler.assistant_message(self)
		yield assembler.usage()


def litellm_limits(name: str) -> tuple[int | None, int | None]:
	"""(context window, max output) from LiteLLM's catalog, else from the id behind the
	prefix when the full name has no window (a gateway's custom_openai/openai/gpt-x)."""
	import litellm

	for candidate in filter(None, (name, name.partition("/")[2])):
		try:
			info = litellm.get_model_info(candidate)
		except Exception:
			continue
		context = info.get("max_input_tokens") or info.get("max_tokens")
		if context:
			output = info.get("max_output_tokens")
			return int(context), int(output) if output else None
	return None, None


@dataclass(slots=True)
class _ResponseAssembler:
	"""Assembles one streamed completion into ordered content blocks.

	Tool calls arrive as fragments tagged with the call's position in the response, so
	`blocks` holds that position as a placeholder until the final assembly resolves it.
	"""

	blocks: list[TextContent | ThinkingContent | int] = field(default_factory=list)
	tool_display_templates: Mapping[str, str] = field(default_factory=dict)
	partial_calls: dict[int, dict[str, str]] = field(default_factory=dict)
	announced_calls: set[int] = field(default_factory=set)
	ready_calls: set[int] = field(default_factory=set)
	placed_calls: set[int] = field(default_factory=set)
	thinking_open: bool = False
	raw_usage: Any = None
	finish_reason: str | None = None
	response_id: str | None = None
	response_model: str | None = None

	def add_chunk(self, chunk: Any) -> list[AnyEvent]:
		"""Fold one chunk into the assembly; return the live deltas it produced."""
		self.response_id = self.response_id or _attr(chunk, "id")
		self.response_model = self.response_model or _attr(chunk, "model")
		events: list[AnyEvent] = []
		choices = _attr(chunk, "choices") or []
		if choices:
			choice = choices[0]
			delta = _attr(choice, "delta")
			self.finish_reason = _attr(choice, "finish_reason") or self.finish_reason
			events += self._add_reasoning(delta)
			events += self._add_text(delta)
			events += self._add_tool_calls(delta)
			if self.finish_reason is not None:
				events += self._ready_tool_calls(allow_empty=True)
		chunk_usage = _attr(chunk, "usage")
		if chunk_usage is not None:
			self.raw_usage = chunk_usage
		return events

	def _add_reasoning(self, delta: Any) -> list[AnyEvent]:
		events: list[AnyEvent] = []
		for part in _reasoning_deltas(delta):
			if part.redacted:
				self.blocks.append(
					ThinkingContent(thinking="", thinking_signature=part.signature, redacted=True)
				)
				self.thinking_open = False
				continue
			block = self.blocks[-1] if self.thinking_open and self.blocks else None
			if not isinstance(block, ThinkingContent):
				block = ThinkingContent(thinking="")
				self.blocks.append(block)
				self.thinking_open = True
			text = part.text
			if part.signature and text == block.thinking:
				# Anthropic replays the block's accumulated thinking on its signature
				# chunk; Gemini signs a genuinely new fragment.
				text = ""
			if text:
				block.thinking += text
				events.append(ThinkingDelta(thinking=text))
			if part.signature:
				# A signature seals its block; later reasoning opens a new one.
				block.thinking_signature = part.signature
				self.thinking_open = False
		return events

	def _add_text(self, delta: Any) -> list[AnyEvent]:
		text = _attr(delta, "content")
		if not text:
			return []
		if self.blocks and isinstance(self.blocks[-1], TextContent):
			self.blocks[-1].text += text
		else:
			self.blocks.append(TextContent(text=text))
		return [TextDelta(text=text)]

	def _add_tool_calls(self, delta: Any) -> list[AnyEvent]:
		events: list[AnyEvent] = []
		for fragment in _attr(delta, "tool_calls") or []:
			position = _accumulate_tool_call(self.partial_calls, fragment)
			if position not in self.placed_calls:  # first fragment reserves the call's place
				self.placed_calls.add(position)
				self.blocks.append(position)
			parts = self.partial_calls[position]
			# announce only once both halves of the identity have arrived
			if position not in self.announced_calls and parts["id"] and parts["name"]:
				self.announced_calls.add(position)
				events.append(ToolCallStarted(id=parts["id"], name=parts["name"]))
		events += self._ready_tool_calls()
		return events

	def _ready_tool_calls(self, *, allow_empty: bool = False) -> list[AnyEvent]:
		events: list[AnyEvent] = []
		for position, parts in sorted(self.partial_calls.items()):
			if position in self.ready_calls:
				continue
			ready = tool_call_display_ready_event(
				parts["id"],
				parts["name"],
				parts["arguments"],
				display_template=self.tool_display_templates.get(parts["name"]),
				complete=allow_empty,
			)
			if ready is None:
				continue
			self.ready_calls.add(position)
			events.append(ready)
		return events

	def assistant_message(self, model: LiteLLMModel) -> AssistantMessage:
		calls_by_position = _finalize_tool_calls(self.partial_calls)
		content: list[TextContent | ThinkingContent | ToolCall] = []
		for block in self.blocks:
			if isinstance(block, int):
				call = calls_by_position.get(block)
				if call is not None:
					content.append(call)
			else:
				content.append(block)
		actual = self.response_model
		message = AssistantMessage(
			content=content,
			api=model.api,
			provider=model.provider,
			model=model.model,
			response_model=actual if isinstance(actual, str) and actual != model.name else None,
			response_id=self.response_id,
			stop_reason=(
				"aborted"
				if self.finish_reason == "aborted"
				else _stop_reason(self.finish_reason, has_tools=bool(calls_by_position))
			),
		)
		return with_tool_call_displays(message, self.tool_display_templates)

	def usage(self) -> Usage:
		return _usage_event(self.raw_usage)


# --- litellm response helpers ---------------------------------------------


def _attr(obj: Any, key: str, default: Any = None) -> Any:
	"""Read a field whether the litellm object exposes it as an attribute or a dict."""
	if obj is None:
		return default
	if isinstance(obj, dict):
		return obj.get(key, default)
	return getattr(obj, key, default)


def _accumulate_tool_call(partial_calls: dict[int, dict[str, str]], fragment: Any) -> int:
	"""Fold one streamed tool-call fragment into the accumulator for its position."""
	position = _attr(fragment, "index", 0) or 0
	parts = partial_calls.setdefault(position, {"id": "", "name": "", "arguments": ""})
	call_id = _attr(fragment, "id")
	if call_id:
		parts["id"] = call_id
	function = _attr(fragment, "function")
	if function is not None:
		name = _attr(function, "name")
		if name:
			parts["name"] = name
		arguments = _attr(function, "arguments")
		if arguments:
			# the provider splits the JSON at arbitrary points
			parts["arguments"] += arguments
	return position


def _finalize_tool_calls(partial_calls: dict[int, dict[str, str]]) -> dict[int, ToolCall]:
	"""Parse each accumulated call, skipping any the provider never identified."""
	calls: dict[int, ToolCall] = {}
	for position, parts in sorted(partial_calls.items()):
		if not parts["id"] and not parts["name"]:
			continue
		calls[position] = _build_tool_call(parts["id"], parts["name"], parts["arguments"])
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
	"""Parse a tool call's raw JSON arguments. Malformed arguments become a
	`ToolCall.error` the agent feeds back to the model, not an exception."""
	raw_args = raw_args or ""
	if not raw_args:
		return ToolCall(id=call_id, name=name, arguments={})
	try:
		parsed = json.loads(raw_args)
	except (TypeError, ValueError):
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
	*,
	resolve_attachment: Callable[[str], bytes] | None = None,
) -> list[dict[str, Any]]:
	"""Translate canonical transcript messages at the provider boundary."""
	out: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
	dropped_calls: set[str] = set()
	# a tool message must directly follow its assistant call, so tool images wait and
	# go out as one user turn after the batch
	pending_images: list[ResolvedImage] = []
	supports_images = model.supports_images
	for message in messages:
		if not isinstance(message, ToolResult):
			_flush_tool_images(out, pending_images)
		if isinstance(message, UserMessage):
			text, images = resolve_user_content(
				message,
				resolve_attachment=resolve_attachment,
				supports_images=supports_images,
			)
			if images:
				content: str | list[dict[str, Any]] = []
				if text:
					content.append({"type": "text", "text": text})
				content.extend(
					{"type": "image_url", "image_url": {"url": image.data_url}} for image in images
				)
			else:
				content = text
			out.append({"role": "user", "content": content})
		elif isinstance(message, AssistantMessage):
			if message.stop_reason in {"error", "aborted"}:
				# drop this turn's results too: an answer without its call is rejected
				dropped_calls.update(call.id for call in message.tool_calls)
				continue
			out.append(_assistant_wire(message, model))
		elif isinstance(message, ToolResult):
			if message.tool_call_id in dropped_calls:
				continue
			out.append(
				{
					"role": "tool",
					"tool_call_id": message.tool_call_id,
					"content": message.content,
				}
			)
			pending_images.extend(
				resolve_tool_images(
					message, resolve_attachment=resolve_attachment, supports_images=supports_images
				)
			)
	_flush_tool_images(out, pending_images)
	return out


# labels the user turn that carries tool images, so the model knows where they came from
_TOOL_IMAGE_PREFACE = "Images returned by the tool calls above:"


def _flush_tool_images(out: list[dict[str, Any]], pending_images: list[ResolvedImage]) -> None:
	"""Send the images gathered from the preceding tool results as one user message,
	then empty the list. Tool messages themselves cannot carry images."""
	if not pending_images:
		return
	out.append(
		{
			"role": "user",
			"content": [
				{"type": "text", "text": _TOOL_IMAGE_PREFACE},
				*({"type": "image_url", "image_url": {"url": image.data_url}} for image in pending_images),
			],
		}
	)
	pending_images.clear()


_CACHE_CONTROL = {"type": "ephemeral"}


def _uses_explicit_prompt_caching(model: str) -> bool:
	"""Return whether the model uses explicit cache breakpoints."""
	prefix = model.split("/", 1)[0]
	if prefix == "anthropic":
		return True
	try:
		import litellm

		resolved_model, provider, _, _ = litellm.get_llm_provider(model=model)
	except Exception:
		return False
	if provider == "anthropic":
		return True
	model_name = resolved_model.lower()
	if provider == "openrouter":
		return any(name in model_name for name in ("claude", "gemini", "minimax"))
	if provider in {"azure_ai", "databricks"}:
		return "claude" in model_name
	if provider not in {"bedrock", "vertex_ai"}:
		return False
	try:
		info = litellm.get_model_info(model)
	except Exception:
		# Handle new Claude models missing from LiteLLM's catalog.
		if provider == "vertex_ai":
			return resolved_model.startswith("claude-")
		return resolved_model.startswith("anthropic.") or ".anthropic." in resolved_model
	if provider == "vertex_ai":
		return info.get("litellm_provider") == "vertex_ai-anthropic_models"
	return info.get("supports_prompt_caching") is True


def _mark_cache_breakpoints(messages: list[dict[str, Any]]) -> None:
	"""Mark cache boundaries in the prompt."""
	if messages and messages[0]["role"] == "system" and messages[0]["content"]:
		messages[0]["cache_control"] = _CACHE_CONTROL
	for message in reversed(messages):
		if message["role"] in ("user", "tool"):
			message["cache_control"] = _CACHE_CONTROL
			break


def _cache_last_tool(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""Mark the tool prefix without changing the request schemas."""
	marked = list(tools)
	marked[-1] = {**marked[-1], "cache_control": _CACHE_CONTROL}
	return marked


# Providers that reject `reasoning_content` on an assistant message they authored.
_NO_REASONING_REPLAY = {"groq"}


def _assistant_wire(message: AssistantMessage, model: LiteLLMModel) -> dict[str, Any]:
	same_model = (
		message.api == model.api and message.provider == model.provider and message.model == model.model
	)
	text_parts: list[str] = []
	reasoning_parts: list[str] = []
	thinking_blocks: list[dict[str, Any]] = []
	for block in message.content:
		if isinstance(block, TextContent):
			text_parts.append(block.text)
		elif isinstance(block, ThinkingContent):
			if not same_model:
				# deliberately degrades cross-model thinking to ordinary text
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
				"function": {"name": call.name, "arguments": json.dumps(call.arguments)},
			}
			for call in message.tool_calls
		]
	if reasoning_parts and model.provider not in _NO_REASONING_REPLAY:
		assistant["reasoning_content"] = "".join(reasoning_parts)
	# Anthropic-family providers read thinking only from `thinking_blocks`; without
	# them litellm silently drops the `thinking` parameter next turn.
	if thinking_blocks:
		assistant["thinking_blocks"] = thinking_blocks
	return assistant


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


def _usage_event(usage_obj: Any, cost: float = 0.0) -> Usage:
	# LiteLLM includes cached tokens in prompt_tokens.
	details = _attr(usage_obj, "prompt_tokens_details")
	# streamed calls carry their cost on the usage
	stated = _attr(usage_obj, "cost")
	return Usage(
		input_tokens=_attr(usage_obj, "prompt_tokens", 0) or 0,
		output_tokens=_attr(usage_obj, "completion_tokens", 0) or 0,
		cache_read_tokens=_attr(usage_obj, "cache_read_input_tokens", 0)
		or _attr(details, "cached_tokens", 0)
		or 0,
		cache_write_tokens=_attr(usage_obj, "cache_creation_input_tokens", 0)
		or _attr(details, "cache_write_tokens", 0)
		or _attr(details, "cache_creation_tokens", 0)
		or 0,
		cost=cost or (stated if isinstance(stated, (int, float)) else 0.0),
	)


def _cost(response: Any) -> float:
	return (getattr(response, "_hidden_params", None) or {}).get("response_cost") or 0.0
