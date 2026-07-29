"""Codex (ChatGPT subscription) OAuth and Responses API model."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections.abc import AsyncIterator, Mapping
from typing import Any
from urllib.parse import urlencode

import httpx

from flow_server.events import (
	AssistantMessage,
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
from flow_server.model.errors import (
	ProviderError,
	normalize_provider_error,
	provider_error_detail,
	provider_error_from_http,
)
from flow_server.model.model import (
	Model,
	ModelCancelled,
	ModelRequest,
	await_with_cancellation,
	iterate_with_cancellation,
)

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

	api = "openai-codex-responses"
	provider = "codex"

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
		self.model = name
		self._model = name.split("/", 1)[1] if "/" in name else name
		self._api_key = api_key
		self._api_base = api_base or API_BASE
		self._headers = headers or {}
		self._params = params or {}
		self._client = client

	async def run(self, request: ModelRequest) -> AsyncIterator[_Event]:
		input_items = _responses_input(request.messages, self)
		payload: dict[str, Any] = {
			"model": self._model,
			"store": False,
			"stream": True,
			"instructions": request.system_prompt,
			"input": input_items,
			"text": {"verbosity": "low"},
			"include": ["reasoning.encrypted_content"],
			"tool_choice": "auto",
			"parallel_tool_calls": True,
			**self._params,
		}
		if request.tools:
			payload["tools"] = [_responses_tool(tool) for tool in request.tools]

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
		stream_context = client.stream("POST", url, json=payload, headers=headers)
		response: httpx.Response | None = None
		try:
			if request.cancellation is not None and request.cancellation.is_set():
				raise ModelCancelled
			response = await await_with_cancellation(
				stream_context.__aenter__(),
				request.cancellation,
			)
			assert response is not None
			if response.status_code >= 400:
				body = await await_with_cancellation(
					response.aread(),
					request.cancellation,
				)
				raise provider_error_from_http(
					status_code=response.status_code,
					provider=self.provider,
					body=body,
					headers=response.headers,
				)
			async for event in _codex_events(
				response,
				model=self,
				emit_deltas=request.stream,
				cancellation=request.cancellation,
			):
				yield event
		except ModelCancelled:
			yield self._aborted()
			yield Usage()
		except ProviderError:
			raise
		except httpx.HTTPError as exc:
			raise normalize_provider_error(exc, provider=self.provider) from exc
		finally:
			if response is not None:
				await stream_context.__aexit__(*sys.exc_info())
			if owns_client:
				await client.aclose()

	def _aborted(self) -> AssistantMessage:
		return AssistantMessage(
			api=self.api,
			provider=self.provider,
			model=self.model,
			stop_reason="aborted",
		)


class _ToolBuilder:
	def __init__(self, item: Mapping[str, Any]):
		self.item_id = _string(item.get("id"))
		self.call_id = _string(item.get("call_id")) or "call_0"
		self.name = _string(item.get("name"))
		self.arguments = ""
		self.content_index: int | None = None

	@property
	def id(self) -> str:
		return f"{self.call_id}|{self.item_id}" if self.item_id else self.call_id

	def build(self) -> ToolCall:
		return _tool_call(self.id, self.name, self.arguments)


async def _codex_events(
	response: httpx.Response,
	*,
	model: CodexModel,
	emit_deltas: bool,
	cancellation: asyncio.Event | None = None,
) -> AsyncIterator[_Event]:
	builders: dict[str, _ToolBuilder] = {}
	completed: set[str] = set()
	content: list[TextContent | ThinkingContent | ToolCall] = []
	content_indices: dict[str, int] = {}
	usage = Usage()
	response_id: str | None = None
	response_model: str | None = None
	stop_reason = "stop"

	try:
		async for raw in iterate_with_cancellation(_iter_sse(response), cancellation):
			event_type = raw.get("type")
			if event_type in {"error", "response.failed"}:
				raise normalize_provider_error(
					RuntimeError(_codex_error(raw)),
					provider=model.provider,
				)
			if event_type == "response.output_item.added":
				item = raw.get("item")
				if isinstance(item, Mapping) and item.get("type") == "reasoning":
					item_id = _string(item.get("id"))
					block = ThinkingContent(
						thinking=_reasoning_text(item),
						thinking_signature=json.dumps(dict(item), separators=(",", ":")),
					)
					content_indices[item_id] = len(content)
					content.append(block)
				elif isinstance(item, Mapping) and item.get("type") == "message":
					item_id = _string(item.get("id"))
					content_indices[item_id] = len(content)
					content.append(TextContent(text=_done_text(item), text_signature=_text_signature(item)))
				elif isinstance(item, Mapping) and item.get("type") == "function_call":
					builder = _ToolBuilder(item)
					builder.content_index = len(content)
					content.append(builder.build())
					for key in (builder.item_id, builder.call_id):
						if key:
							builders[key] = builder
					if emit_deltas:
						yield ToolCallStarted(id=builder.id, name=builder.name)
			elif event_type == "response.function_call_arguments.delta":
				builder = _find_builder(raw, builders)
				if builder and isinstance(raw.get("delta"), str):
					builder.arguments += raw["delta"]
					if builder.content_index is not None:
						content[builder.content_index] = builder.build()
			elif event_type == "response.function_call_arguments.done":
				builder = _find_builder(raw, builders)
				if builder and isinstance(raw.get("arguments"), str):
					builder.arguments = raw["arguments"]
					if builder.content_index is not None:
						content[builder.content_index] = builder.build()
			elif event_type in {
				"response.reasoning_summary_text.delta",
				"response.reasoning_text.delta",
			}:
				delta = raw.get("delta")
				if isinstance(delta, str) and delta:
					item_id = _string(raw.get("item_id"))
					index = content_indices.get(item_id)
					if index is None or not isinstance(content[index], ThinkingContent):
						index = len(content)
						content_indices[item_id] = index
						content.append(ThinkingContent(thinking=""))
					thinking_block = content[index]
					assert isinstance(thinking_block, ThinkingContent)
					thinking_block.thinking += delta
					if emit_deltas:
						yield ThinkingDelta(thinking=delta)
			elif event_type == "response.output_text.delta":
				delta = raw.get("delta")
				if isinstance(delta, str) and delta:
					item_id = _string(raw.get("item_id"))
					index = content_indices.get(item_id)
					if index is None or not isinstance(content[index], TextContent):
						index = len(content)
						content_indices[item_id] = index
						content.append(
							TextContent(
								text="",
								text_signature=_encode_text_signature(item_id) if item_id else None,
							)
						)
					text_block = content[index]
					assert isinstance(text_block, TextContent)
					text_block.text += delta
					if emit_deltas:
						yield TextDelta(text=delta)
			elif event_type in {"response.output_item.done", "response.output_item.completed"}:
				item = raw.get("item")
				if isinstance(item, Mapping) and item.get("type") == "reasoning":
					item_id = _string(item.get("id"))
					index = content_indices.get(item_id)
					streamed = content[index] if index is not None else None
					if not isinstance(streamed, ThinkingContent):
						streamed = None
					block = ThinkingContent(
						# The done item omits summary text when it was only streamed.
						thinking=_reasoning_text(item) or (streamed.thinking if streamed else ""),
						thinking_signature=json.dumps(dict(item), separators=(",", ":")),
					)
					if streamed is None:
						content_indices[item_id] = len(content)
						content.append(block)
					else:
						content[index] = block
				elif isinstance(item, Mapping) and item.get("type") == "function_call":
					builder = _find_builder(raw, builders) or _ToolBuilder(item)
					if isinstance(item.get("arguments"), str):
						builder.arguments = item["arguments"]
					if builder.id not in completed:
						if builder.content_index is None:
							builder.content_index = len(content)
							content.append(builder.build())
						else:
							content[builder.content_index] = builder.build()
						completed.add(builder.id)
				elif isinstance(item, Mapping) and item.get("type") == "message":
					text = _done_text(item)
					item_id = _string(item.get("id"))
					index = content_indices.get(item_id)
					if index is None or not isinstance(content[index], TextContent):
						if text:
							content_indices[item_id] = len(content)
							content.append(TextContent(text=text, text_signature=_text_signature(item)))
					else:
						text_block = content[index]
						assert isinstance(text_block, TextContent)
						text_block.text_signature = _text_signature(item) or text_block.text_signature
						if text and not text_block.text:
							text_block.text = text
							if emit_deltas:
								yield TextDelta(text=text)
			elif event_type in {"response.completed", "response.done", "response.incomplete"}:
				usage = _codex_usage(raw)
				response_data = raw.get("response")
				if isinstance(response_data, Mapping):
					response_id = _string(response_data.get("id")) or None
					actual_model = _string(response_data.get("model"))
					response_model = actual_model if actual_model and actual_model != model._model else None
				stop_reason = "length" if event_type == "response.incomplete" else "stop"
				break
	except ModelCancelled:
		stop_reason = "aborted"

	tool_calls = [block for block in content if isinstance(block, ToolCall)]
	yield AssistantMessage(
		content=content,
		api=model.api,
		provider=model.provider,
		model=model.model,
		response_model=response_model,
		response_id=response_id,
		stop_reason="tool_use" if tool_calls and stop_reason != "aborted" else stop_reason,
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


def _responses_input(messages: list[TranscriptMessage], model: CodexModel) -> list[dict]:
	items: list[dict] = []
	text_index = 0
	for message in messages:
		if isinstance(message, UserMessage):
			items.append({"role": "user", "content": [{"type": "input_text", "text": message.content}]})
		elif isinstance(message, AssistantMessage):
			if message.stop_reason in {"error", "aborted"}:
				continue
			same_model = (
				message.api == model.api
				and message.provider == model.provider
				and message.model == model.model
			)
			for block in message.content:
				if isinstance(block, ThinkingContent):
					if same_model and block.thinking_signature:
						try:
							reasoning_item = json.loads(block.thinking_signature)
						except TypeError, ValueError:
							reasoning_item = None
						if isinstance(reasoning_item, dict):
							items.append(reasoning_item)
							continue
					if not block.redacted and block.thinking:
						items.append(_assistant_text_item(block.thinking, f"msg_{text_index}"))
						text_index += 1
				elif isinstance(block, TextContent):
					signature = _parse_text_signature(block.text_signature) if same_model else None
					item_id = signature["id"] if signature else f"msg_{text_index}"
					phase = signature.get("phase") if signature else None
					items.append(_assistant_text_item(block.text, item_id, phase))
					text_index += 1
				elif isinstance(block, ToolCall):
					call_id, item_id = _split_call_id(block.id)
					item = {
						"type": "function_call",
						"call_id": call_id,
						"name": block.name,
						"arguments": json.dumps(block.arguments),
					}
					if item_id:
						item["id"] = item_id
					items.append(item)
		elif isinstance(message, ToolResult):
			call_id, _ = _split_call_id(message.tool_call_id)
			items.append(
				{
					"type": "function_call_output",
					"call_id": call_id,
					"output": message.content,
				}
			)
	return items


def _assistant_text_item(text: str, item_id: str, phase: str | None = None) -> dict:
	item = {
		"type": "message",
		"role": "assistant",
		"content": [{"type": "output_text", "text": text, "annotations": []}],
		"status": "completed",
		"id": item_id,
	}
	if phase is not None:
		item["phase"] = phase
	return item


def _encode_text_signature(item_id: str, phase: str | None = None) -> str:
	payload: dict[str, Any] = {"v": 1, "id": item_id}
	if phase in {"commentary", "final_answer"}:
		payload["phase"] = phase
	return json.dumps(payload, separators=(",", ":"))


def _text_signature(item: Mapping[str, Any]) -> str | None:
	item_id = _string(item.get("id"))
	if not item_id:
		return None
	phase = item.get("phase")
	return _encode_text_signature(item_id, phase if isinstance(phase, str) else None)


def _parse_text_signature(signature: str | None) -> dict[str, str] | None:
	if not signature:
		return None
	try:
		value = json.loads(signature)
	except TypeError, ValueError:
		return None
	if not isinstance(value, dict) or value.get("v") != 1 or not isinstance(value.get("id"), str):
		return None
	result = {"id": value["id"]}
	if value.get("phase") in {"commentary", "final_answer"}:
		result["phase"] = value["phase"]
	return result


def _reasoning_text(item: Mapping[str, Any]) -> str:
	"""Summary text when the model summarises, else the raw reasoning text."""
	for key in ("summary", "content"):
		parts = item.get(key)
		if not isinstance(parts, list):
			continue
		text = "".join(
			part.get("text", "")
			for part in parts
			if isinstance(part, Mapping) and isinstance(part.get("text"), str)
		)
		if text:
			return text
	return ""


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
	except TypeError, ValueError:
		return ToolCall(
			id=call_id,
			name=name,
			arguments={},
			error=f"Invalid JSON in arguments for {name!r}; resend the call with valid JSON.",
		)
	if not isinstance(args, dict):
		return ToolCall(
			id=call_id,
			name=name,
			arguments={},
			error=f"Arguments for {name!r} must be a JSON object.",
		)
	return ToolCall(id=call_id, name=name, arguments=args)


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
	return provider_error_detail(event) or "OpenAI Codex returned an error"


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
