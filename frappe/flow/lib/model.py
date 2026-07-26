# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any

import frappe

DEFAULT_TIMEOUT = 60


@dataclass
class ToolCall:
	id: str
	name: str
	arguments: dict[str, Any]
	# Set when the model emitted unparseable arguments; the agent feeds this back so it can retry
	# instead of the whole run failing.
	error: str | None = None


@dataclass
class ToolCallBegin:
	"""Streamed marker: the model has started emitting a tool call (name known, arguments still
	streaming). Lets the UI show the tool immediately instead of after the full arguments arrive."""

	id: str
	name: str


@dataclass
class ChatResponse:
	content: str | None
	tool_calls: list[ToolCall] = field(default_factory=list)
	finish_reason: str | None = None
	usage: dict[str, int] = field(default_factory=dict)


class Model:
	def __init__(
		self,
		name: str | None = None,
		*,
		model_id: str | None = None,
		api_key: str | None = None,
		base_url: str | None = None,
		params: dict[str, Any] | None = None,
		timeout: int = DEFAULT_TIMEOUT,
	):
		if name is not None:
			if model_id or api_key or base_url or params:
				raise ValueError("Pass either a Flow Model doc name or explicit kwargs, not both.")
			doc = frappe.get_doc("Flow Model", name)
			if not doc.enabled:
				raise ValueError(f"Flow Model {name!r} is disabled")
			model_id = doc.model_id
			api_key = doc.get_password("api_key", raise_exception=False)
			base_url = doc.base_url or None
			params = json.loads(doc.params) if doc.params else {}

		if not model_id:
			raise ValueError("model_id is required")

		# Fall back to the central Flow Provider store for anything not set on the model itself.
		provider_creds = resolve_provider_credentials(model_id)
		api_key = api_key or provider_creds.get("api_key")
		base_url = base_url or provider_creds.get("base_url")
		if provider_creds.get("extra_params"):
			params = {**provider_creds["extra_params"], **(params or {})}

		self.model_id = model_id
		self._api_key = api_key or None
		self.base_url = base_url
		self.params = params or {}
		self.timeout = timeout

	def chat(
		self,
		messages: str | list[dict[str, Any]],
		tools: list[dict[str, Any]] | None = None,
		*,
		stream: bool = False,
	) -> ChatResponse | Generator[str, None, ChatResponse]:
		"""Call the model. When `stream=True`, returns a generator that yields text deltas
		and returns the assembled `ChatResponse` via PEP 380 (`StopIteration.value`)."""
		import litellm

		if isinstance(messages, str):
			messages = [{"role": "user", "content": messages}]

		kwargs: dict[str, Any] = {
			"model": self.model_id,
			"api_key": self._api_key,
			"messages": messages,
			"timeout": self.timeout,
			**self.params,
		}
		if self.base_url:
			kwargs["api_base"] = self.base_url
		if tools:
			kwargs["tools"] = tools

		if stream:
			kwargs["stream"] = True
			kwargs["stream_options"] = {"include_usage": True}
			return _consume_stream(litellm.completion(**kwargs))

		return _normalize(litellm.completion(**kwargs))


def resolve_provider_credentials(model_id: str) -> dict[str, Any]:
	"""Look up central Flow Provider credentials for a model's provider."""
	try:
		import litellm

		provider = litellm.get_llm_provider(model_id)[1]
	except Exception:
		return {}

	if not provider or not frappe.db.exists("Flow Provider", provider):
		return {}

	doc = frappe.get_doc("Flow Provider", provider)
	if not doc.enabled:
		return {}

	return {
		"api_key": doc.get_password("api_key", raise_exception=False) or None,
		"base_url": doc.base_url or None,
		"extra_params": json.loads(doc.extra_params) if doc.extra_params else {},
	}


def _consume_stream(chunks: Any) -> Generator[str | ToolCallBegin, None, ChatResponse]:
	"""Yield text deltas (and a ToolCallBegin the moment each tool call's name is known) from a
	litellm stream; return the assembled ChatResponse at the end."""
	content_parts: list[str] = []
	tool_calls_acc: dict[int, dict[str, str]] = {}
	announced: set[int] = set()
	usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
	finish_reason: str | None = None

	for chunk in chunks:
		choices = getattr(chunk, "choices", None) or []
		if choices:
			choice = choices[0]
			delta = getattr(choice, "delta", None)
			if delta is not None:
				text = _attr(delta, "content")
				if text:
					content_parts.append(text)
					yield text
				for tc_delta in _attr(delta, "tool_calls") or []:
					index = _accumulate_tool_call(tool_calls_acc, tc_delta)
					slot = tool_calls_acc[index]
					if index not in announced and slot["id"] and slot["name"]:
						announced.add(index)
						yield ToolCallBegin(id=slot["id"], name=slot["name"])
			reason = _attr(choice, "finish_reason")
			if reason:
				finish_reason = reason

		usage_obj = getattr(chunk, "usage", None)
		if usage_obj is not None:
			usage = {
				"prompt_tokens": _attr(usage_obj, "prompt_tokens", 0) or 0,
				"completion_tokens": _attr(usage_obj, "completion_tokens", 0) or 0,
				"total_tokens": _attr(usage_obj, "total_tokens", 0) or 0,
			}

	return ChatResponse(
		content="".join(content_parts) or None,
		tool_calls=_finalize_tool_calls(tool_calls_acc),
		finish_reason=finish_reason,
		usage=usage,
	)


def _accumulate_tool_call(acc: dict[int, dict[str, str]], delta: Any) -> int:
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


def _build_tool_call(call_id: str, name: str, raw_args: str) -> ToolCall:
	"""Parse a tool call's raw arguments. Malformed arguments become a `ToolCall.error` the agent
	feeds back to the model to retry, rather than an exception that fails the whole run."""
	raw_args = raw_args or ""
	if not raw_args:
		return ToolCall(id=call_id, name=name, arguments={})
	try:
		arguments = json.loads(raw_args)
	except (TypeError, ValueError):
		return ToolCall(
			id=call_id,
			name=name,
			arguments={},
			error=f"Invalid JSON in arguments for {name!r}: {raw_args[:200]}. Resend the call with valid JSON.",
		)
	if not isinstance(arguments, dict):
		return ToolCall(
			id=call_id,
			name=name,
			arguments={},
			error=f"Arguments for {name!r} must be a JSON object, got: {raw_args[:200]}.",
		)
	return ToolCall(id=call_id, name=name, arguments=arguments)


def _normalize(response: Any) -> ChatResponse:
	choice = response.choices[0]
	message = choice.message

	tool_calls = []
	for raw_call in getattr(message, "tool_calls", None) or []:
		function = getattr(raw_call, "function", None) or {}
		name = _attr(function, "name", "")
		raw_args = _attr(function, "arguments", "") or ""
		tool_calls.append(_build_tool_call(_attr(raw_call, "id", ""), name, raw_args))

	usage_obj = getattr(response, "usage", None)
	usage = {
		"prompt_tokens": _attr(usage_obj, "prompt_tokens", 0) or 0,
		"completion_tokens": _attr(usage_obj, "completion_tokens", 0) or 0,
		"total_tokens": _attr(usage_obj, "total_tokens", 0) or 0,
	}

	return ChatResponse(
		content=getattr(message, "content", None),
		tool_calls=tool_calls,
		finish_reason=getattr(choice, "finish_reason", None),
		usage=usage,
	)


def _attr(obj: Any, key: str, default: Any = None) -> Any:
	if obj is None:
		return default
	if isinstance(obj, dict):
		return obj.get(key, default)
	return getattr(obj, key, default)
