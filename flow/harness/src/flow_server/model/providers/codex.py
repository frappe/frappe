"""Codex (ChatGPT subscription) OAuth and Responses API model."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Mapping
from typing import Any
from urllib.parse import urlencode

import httpx

from flow_server.events import AssistantMessage, TextDelta, ToolCall, ToolCallStarted, Usage, _Event
from flow_server.model import register_provider
from flow_server.model.auth import (
	AuthError,
	AuthProvider,
	RuntimeAuth,
	account_id_from_tokens,
	decode_jwt_claims,
	post_token,
	register_auth_provider,
)
from flow_server.model.credentials import OAuthCredential
from flow_server.model.model import Model

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
ISSUER = "https://auth.openai.com"
AUTHORIZE_URL = f"{ISSUER}/oauth/authorize"
TOKEN_URL = f"{ISSUER}/oauth/token"
REDIRECT_URI = "http://localhost:1455/auth/callback"
SCOPE = "openid profile email offline_access"
ORIGINATOR = "flow_server"
API_BASE = "https://chatgpt.com/backend-api"
DEFAULT_EXPIRES_S = 3600


class CodexAuthProvider(AuthProvider):
	name = "codex"

	def authorize_url(self, *, challenge: str, state: str) -> str:
		params = {
			"response_type": "code",
			"client_id": CLIENT_ID,
			"redirect_uri": REDIRECT_URI,
			"scope": SCOPE,
			"code_challenge": challenge,
			"code_challenge_method": "S256",
			"state": state,
			"id_token_add_organizations": "true",
			"codex_cli_simplified_flow": "true",
			"originator": ORIGINATOR,
		}
		return f"{AUTHORIZE_URL}?{urlencode(params)}"

	async def exchange(
		self,
		code: str,
		verifier: str,
		*,
		client: httpx.AsyncClient | None = None,
		now_ms: int | None = None,
	) -> OAuthCredential:
		tokens = await post_token(
			TOKEN_URL,
			{
				"grant_type": "authorization_code",
				"client_id": CLIENT_ID,
				"code": code,
				"code_verifier": verifier,
				"redirect_uri": REDIRECT_URI,
			},
			client,
		)
		return _credential(tokens, now_ms=now_ms)

	async def refresh(
		self,
		credential: OAuthCredential,
		*,
		client: httpx.AsyncClient | None = None,
		now_ms: int | None = None,
	) -> OAuthCredential:
		tokens = await post_token(
			TOKEN_URL,
			{
				"grant_type": "refresh_token",
				"client_id": CLIENT_ID,
				"refresh_token": credential.refresh,
			},
			client,
		)
		return _credential(tokens, old_refresh=credential.refresh, now_ms=now_ms)

	def runtime_auth(self, credential: OAuthCredential) -> RuntimeAuth:
		if not credential.account_id:
			raise AuthError("Codex OAuth credential is missing its ChatGPT account id")
		return RuntimeAuth(
			token=credential.access,
			account_id=credential.account_id,
			base_url=API_BASE,
			headers={
				"chatgpt-account-id": credential.account_id,
				"originator": ORIGINATOR,
			},
		)


class CodexModel(Model):
	"""ChatGPT subscription model over the Codex Responses SSE endpoint."""

	def __init__(
		self,
		name: str,
		*,
		api_key: str | None = None,
		api_base: str | None = None,
		headers: dict[str, str] | None = None,
		params: dict[str, Any] | None = None,
		client: httpx.AsyncClient | None = None,
	):
		if not api_key:
			raise ValueError("Codex requires OAuth; run `flowd login codex`.")
		self.name = name
		self._model = name.split("/", 1)[1] if "/" in name else name
		self._api_key = api_key
		self._api_base = api_base or API_BASE
		self._headers = headers or {}
		self._params = params or {}
		self._client = client

	async def run(
		self,
		messages: list[dict[str, Any]],
		tools: list[dict[str, Any]] | None = None,
		*,
		stream: bool = True,
	) -> AsyncIterator[_Event]:
		instructions, input_items = _responses_input(messages)
		payload: dict[str, Any] = {
			"model": self._model,
			"store": False,
			"stream": True,
			"instructions": instructions,
			"input": input_items,
			"text": {"verbosity": "low"},
			"include": ["reasoning.encrypted_content"],
			"tool_choice": "auto",
			"parallel_tool_calls": True,
			**self._params,
		}
		if tools:
			payload["tools"] = [_responses_tool(tool) for tool in tools]

		headers = {
			**self._headers,
			"Authorization": f"Bearer {self._api_key}",
			"OpenAI-Beta": "responses=experimental",
			"accept": "text/event-stream",
			"content-type": "application/json",
		}
		url = f"{self._api_base.rstrip('/')}/codex/responses"
		owns_client = self._client is None
		client = self._client or httpx.AsyncClient(timeout=120)
		try:
			async with client.stream("POST", url, json=payload, headers=headers) as response:
				if response.status_code >= 400:
					body = (await response.aread()).decode(errors="replace")
					raise RuntimeError(f"Codex HTTP {response.status_code}: {body[:500]}")
				async for event in _codex_events(response, emit_deltas=stream):
					yield event
		finally:
			if owns_client:
				await client.aclose()


class _ToolBuilder:
	def __init__(self, item: Mapping[str, Any]):
		self.item_id = _string(item.get("id"))
		self.call_id = _string(item.get("call_id")) or "call_0"
		self.name = _string(item.get("name"))
		self.arguments = ""

	@property
	def id(self) -> str:
		return f"{self.call_id}|{self.item_id}" if self.item_id else self.call_id

	def build(self) -> ToolCall:
		return _tool_call(self.id, self.name, self.arguments)


async def _codex_events(
	response: httpx.Response, *, emit_deltas: bool
) -> AsyncIterator[_Event]:
	text_parts: list[str] = []
	builders: dict[str, _ToolBuilder] = {}
	completed: set[str] = set()
	tool_calls: list[ToolCall] = []
	reasoning_items: dict[str, dict] = {}
	usage = Usage()

	async for raw in _iter_sse(response):
		event_type = raw.get("type")
		if event_type in {"error", "response.failed"}:
			raise RuntimeError(_codex_error(raw))
		if event_type == "response.output_item.added":
			item = raw.get("item")
			if isinstance(item, Mapping) and item.get("type") == "reasoning":
				item_id = _string(item.get("id"))
				if item_id:
					reasoning_items[item_id] = dict(item)
			elif isinstance(item, Mapping) and item.get("type") == "function_call":
				builder = _ToolBuilder(item)
				for key in (builder.item_id, builder.call_id):
					if key:
						builders[key] = builder
				if emit_deltas:
					yield ToolCallStarted(id=builder.id, name=builder.name)
		elif event_type == "response.function_call_arguments.delta":
			builder = _find_builder(raw, builders)
			if builder and isinstance(raw.get("delta"), str):
				builder.arguments += raw["delta"]
		elif event_type == "response.function_call_arguments.done":
			builder = _find_builder(raw, builders)
			if builder and isinstance(raw.get("arguments"), str):
				builder.arguments = raw["arguments"]
		elif event_type == "response.output_text.delta":
			delta = raw.get("delta")
			if isinstance(delta, str) and delta:
				text_parts.append(delta)
				if emit_deltas:
					yield TextDelta(text=delta)
		elif event_type in {"response.output_item.done", "response.output_item.completed"}:
			item = raw.get("item")
			if isinstance(item, Mapping) and item.get("type") == "reasoning":
				item_id = _string(item.get("id"))
				if item_id:
					reasoning_items[item_id] = dict(item)
			elif isinstance(item, Mapping) and item.get("type") == "function_call":
				builder = _find_builder(raw, builders) or _ToolBuilder(item)
				if isinstance(item.get("arguments"), str):
					builder.arguments = item["arguments"]
				if builder.id not in completed:
					tool_calls.append(builder.build())
					completed.add(builder.id)
			elif (
				isinstance(item, Mapping)
				and item.get("type") == "message"
				and not text_parts
			):
				text = _done_text(item)
				if text:
					text_parts.append(text)
					if emit_deltas:
						yield TextDelta(text=text)
		elif event_type in {"response.completed", "response.done", "response.incomplete"}:
			usage = _codex_usage(raw)
			break

	provider_data = {"codex_reasoning": list(reasoning_items.values())} if reasoning_items else {}
	yield AssistantMessage(
		text="".join(text_parts),
		tool_calls=tool_calls,
		provider_data=provider_data,
	)
	yield usage


async def _iter_sse(response: httpx.Response) -> AsyncIterator[dict]:
	data_lines: list[str] = []
	async for line in response.aiter_lines():
		line = line.strip()
		if not line:
			if data_lines:
				yield _json_object("\n".join(data_lines))
				data_lines = []
			continue
		if line.startswith("data:"):
			value = line.removeprefix("data:").strip()
			if value == "[DONE]":
				break
			data_lines.append(value)
	if data_lines:
		yield _json_object("\n".join(data_lines))


def _responses_input(messages: list[dict[str, Any]]) -> tuple[str, list[dict]]:
	instructions = "You are a helpful assistant."
	items: list[dict] = []
	for index, message in enumerate(messages):
		role = message.get("role")
		content = message.get("content") or ""
		if role == "system":
			instructions = str(content)
		elif role == "user":
			items.append(
				{"role": "user", "content": [{"type": "input_text", "text": str(content)}]}
			)
		elif role == "assistant":
			provider_data = message.get("provider_data")
			if isinstance(provider_data, dict):
				reasoning = provider_data.get("codex_reasoning")
				if isinstance(reasoning, list):
					items.extend(item for item in reasoning if isinstance(item, dict))
			if content:
				items.append(
					{
						"type": "message",
						"role": "assistant",
						"content": [
							{
								"type": "output_text",
								"text": str(content),
								"annotations": [],
							}
						],
						"status": "completed",
						"id": f"msg_{index}",
					}
				)
			for call in message.get("tool_calls") or []:
				function = call.get("function") or {}
				call_id, item_id = _split_call_id(str(call.get("id") or "call_0"))
				item = {
					"type": "function_call",
					"call_id": call_id,
					"name": function.get("name") or "",
					"arguments": function.get("arguments") or "{}",
				}
				if item_id:
					item["id"] = item_id
				items.append(item)
		elif role == "tool":
			call_id, _ = _split_call_id(str(message.get("tool_call_id") or "call_0"))
			items.append(
				{
					"type": "function_call_output",
					"call_id": call_id,
					"output": str(content),
				}
			)
	return instructions, items


def _responses_tool(tool: dict[str, Any]) -> dict:
	function = tool.get("function") or {}
	return {
		"type": "function",
		"name": function.get("name") or "",
		"description": function.get("description") or "",
		"parameters": function.get("parameters") or {},
		"strict": None,
	}


def _find_builder(raw: Mapping[str, Any], builders: dict[str, _ToolBuilder]) -> _ToolBuilder | None:
	for key in ("item_id", "call_id"):
		value = raw.get(key)
		if isinstance(value, str) and value in builders:
			return builders[value]
	unique = {id(builder): builder for builder in builders.values()}
	return next(iter(unique.values())) if len(unique) == 1 else None


def _tool_call(call_id: str, name: str, arguments: str) -> ToolCall:
	try:
		args = json.loads(arguments or "{}")
	except (TypeError, ValueError):
		return ToolCall(
			id=call_id,
			name=name,
			args={},
			error=f"Invalid JSON in arguments for {name!r}; resend the call with valid JSON.",
		)
	if not isinstance(args, dict):
		return ToolCall(
			id=call_id,
			name=name,
			args={},
			error=f"Arguments for {name!r} must be a JSON object.",
		)
	return ToolCall(id=call_id, name=name, args=args)


def _done_text(item: Mapping[str, Any]) -> str:
	parts = item.get("content")
	if not isinstance(parts, list):
		return ""
	return "".join(
		part.get("text", "")
		for part in parts
		if isinstance(part, Mapping) and part.get("type") == "output_text"
	)


def _codex_usage(event: Mapping[str, Any]) -> Usage:
	response = event.get("response")
	raw = response.get("usage") if isinstance(response, Mapping) else None
	if not isinstance(raw, Mapping):
		return Usage()
	return Usage(
		input_tokens=_integer(raw.get("input_tokens")),
		output_tokens=_integer(raw.get("output_tokens")),
	)


def _codex_error(event: Mapping[str, Any]) -> str:
	sources: list[Mapping[str, Any]] = [event]
	for key in ("error", "response"):
		value = event.get(key)
		if isinstance(value, Mapping):
			sources.append(value)
			nested = value.get("error")
			if isinstance(nested, Mapping):
				sources.append(nested)
	for source in sources:
		message = source.get("message")
		if isinstance(message, str) and message:
			return message
	return "OpenAI Codex returned an error"


def _json_object(value: str) -> dict:
	try:
		parsed = json.loads(value)
	except json.JSONDecodeError:
		return {}
	return parsed if isinstance(parsed, dict) else {}


def _split_call_id(value: str) -> tuple[str, str | None]:
	if "|" not in value:
		return value, None
	call_id, item_id = value.split("|", 1)
	return call_id, item_id or None


def _string(value: Any) -> str:
	return value if isinstance(value, str) else ""


def _integer(value: Any) -> int:
	return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _credential(
	tokens: dict, *, old_refresh: str | None = None, now_ms: int | None = None
) -> OAuthCredential:
	now = now_ms if now_ms is not None else int(time.time() * 1000)
	access = tokens["access_token"]
	return OAuthCredential(
		access=access,
		refresh=tokens.get("refresh_token") or old_refresh or "",
		expires=_expires_ms(tokens, access, now),
		account_id=account_id_from_tokens(tokens.get("id_token"), access),
	)


def _expires_ms(tokens: dict, access_token: str, now_ms: int) -> int:
	if tokens.get("expires_in"):
		return now_ms + int(tokens["expires_in"]) * 1000
	exp = decode_jwt_claims(access_token).get("exp")
	if exp:
		return int(exp) * 1000
	return now_ms + DEFAULT_EXPIRES_S * 1000


register_auth_provider(CodexAuthProvider())
register_provider("codex", CodexModel)
