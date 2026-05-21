# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import frappe

DEFAULT_TIMEOUT = 60


@dataclass
class ToolCall:
	id: str
	name: str
	arguments: dict[str, Any]


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
				raise ValueError("Pass either an AI Model doc name or explicit kwargs, not both.")
			doc = frappe.get_doc("AI Model", name)
			if not doc.enabled:
				raise ValueError(f"AI Model {name!r} is disabled")
			model_id = doc.model_id
			api_key = doc.get_password("api_key", raise_exception=False)
			base_url = doc.base_url or None
			params = json.loads(doc.params) if doc.params else {}

		if not model_id:
			raise ValueError("model_id is required")

		self.model_id = model_id
		self._api_key = api_key or ""
		self.base_url = base_url
		self.params = params or {}
		self.timeout = timeout

	def chat(
		self,
		messages: str | list[dict[str, Any]],
		tools: list[dict[str, Any]] | None = None,
	) -> ChatResponse:
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

		response = litellm.completion(**kwargs)
		return _normalize(response)


def _normalize(response: Any) -> ChatResponse:
	choice = response.choices[0]
	message = choice.message

	tool_calls = []
	for raw_call in getattr(message, "tool_calls", None) or []:
		function = getattr(raw_call, "function", None) or {}
		name = _attr(function, "name", "")
		raw_args = _attr(function, "arguments", "") or ""
		try:
			arguments = json.loads(raw_args) if raw_args else {}
		except (TypeError, ValueError) as e:
			raise ValueError(f"Tool call {name!r} returned invalid JSON arguments") from e
		if not isinstance(arguments, dict):
			raise ValueError(f"Tool call {name!r} arguments must be a JSON object")
		tool_calls.append(ToolCall(id=_attr(raw_call, "id", ""), name=name, arguments=arguments))

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
