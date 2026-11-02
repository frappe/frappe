"""Codex (ChatGPT subscription): OAuth provider + Responses SSE adapter.

Codex must round-trip three provider-native identities that Flow's neutral events do
not model: the raw reasoning item (encrypted), a message item's id and phase, and a
function call's item id. All three ride in `provider_state` — written when a response
is assembled, read back by `_responses_input` when the same model replays the turn,
and invisible to every other layer.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import httpx

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
from flow_harness.model.auth import (
	AuthError,
	AuthProvider,
	RefreshAuth,
	RuntimeAuth,
	account_id_from_tokens,
	decode_jwt_claims,
	post_token,
)
from flow_harness.model.base import Model, ModelRequest
from flow_harness.model.cancellation import ModelCancelled, await_with_cancellation, iterate_with_cancellation
from flow_harness.model.content import resolve_tool_images, resolve_user_content
from flow_harness.model.credentials import OAuthCredential
from flow_harness.model.errors import (
	normalize_provider_error,
	provider_error_detail,
	provider_error_from_http,
)
from flow_harness.model.retry import run_with_retries
from flow_harness.model.tool_display import tool_call_display_ready_event, with_tool_call_displays

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
ISSUER = "https://auth.openai.com"
AUTHORIZE_URL = f"{ISSUER}/oauth/authorize"
TOKEN_URL = f"{ISSUER}/oauth/token"
REDIRECT_URI = "http://localhost:1455/auth/callback"
SCOPE = "openid profile email offline_access"
ORIGINATOR = "flow"
API_BASE = "https://chatgpt.com/backend-api"
DEFAULT_EXPIRES_S = 3600
# The Codex catalog hides models newer than the version we report, so claim a far-future one.
DEFAULT_CODEX_CLIENT_VERSION = "999.0.0"
MODEL_CATALOG_TIMEOUT_SECONDS = 5.0
DEFAULT_CODEX_MAX_OUTPUT_TOKENS = 128_000
DEFAULT_AUTO_COMPACT_PERCENT = 90

# The authenticated catalog overrides these conservative subscription fallbacks.
# They deliberately describe the ChatGPT Codex serving surface, not the public API.
_CODEX_FALLBACK_CONTEXT_WINDOWS = {
	"gpt-6-astra": 272_000,
	"gpt-6-sol": 272_000,
	"gpt-6-luna": 272_000,
	"gpt-5.6-sol": 272_000,
	"gpt-5.6-terra": 272_000,
	"gpt-5.6-luna": 272_000,
	"gpt-5.6": 272_000,
	"gpt-5.5": 272_000,
	"gpt-5.4-mini": 272_000,
	"gpt-5.4-pro": 272_000,
	"gpt-5.4": 272_000,
	"gpt-5.3-codex-spark": 128_000,
	"gpt-5.3-codex": 400_000,
	"gpt-5.2": 400_000,
}


@dataclass(frozen=True)
class _CodexModelLimits:
	context_window: int | None = None
	max_output_tokens: int | None = None
	auto_compact_threshold_tokens: int | None = None


def codex_supports_images(model: str) -> bool:
	"""Whether a Codex subscription model accepts Responses ``input_image`` items."""
	return "spark" not in model.lower()


# --- OAuth provider --------------------------------------------------------


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


# --- the model -------------------------------------------------------------


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
		refresh_auth: RefreshAuth | None = None,
	):
		if not api_key:
			raise ValueError("Codex requires OAuth; run `flow login codex`.")
		self.name = name
		self.model = name
		self._remote_model = name.split("/", 1)[1] if "/" in name else name
		self._api_key = api_key
		self._api_base = api_base or API_BASE
		self._headers = headers or {}
		self._params = params or {}
		self._client = client
		self._refresh_auth = refresh_auth
		self._limits = _fallback_model_limits(self._remote_model)
		self._model_limits_loaded = False

	@property
	def supports_images(self) -> bool:
		return codex_supports_images(self._remote_model)

	@property
	def context_window(self) -> int | None:
		return self._limits.context_window

	@property
	def max_output_tokens(self) -> int | None:
		return self._limits.max_output_tokens

	@property
	def auto_compact_threshold_tokens(self) -> int | None:
		return self._limits.auto_compact_threshold_tokens

	async def load_model_limits(self, cancellation: asyncio.Event | None = None) -> None:
		"""Load this account's limits from the authenticated Codex catalog once."""
		if self._model_limits_loaded:
			return
		owns_client = self._client is None
		client = self._client or httpx.AsyncClient()
		try:
			response = await await_with_cancellation(
				client.get(
					f"{self._api_base.rstrip('/')}/codex/models",
					params={"client_version": codex_client_version()},
					headers=self._model_catalog_headers(),
					timeout=MODEL_CATALOG_TIMEOUT_SECONDS,
				),
				cancellation,
			)
			response.raise_for_status()
			discovered_limits = _catalog_model_limits(response.json(), self._remote_model)
			if discovered_limits is not None:
				self._limits = _merge_model_limits(discovered_limits, self._limits)
		except ModelCancelled:
			raise
		except Exception:
			pass  # static limits remain the safe fallback
		finally:
			if owns_client:
				await client.aclose()
		self._model_limits_loaded = True

	async def run(self, request: ModelRequest) -> AsyncIterator[AnyEvent]:
		owns_client = self._client is None
		client = self._client or httpx.AsyncClient(timeout=120)

		def start_attempt() -> AsyncIterator[AnyEvent]:
			return self._response(request, client)

		try:
			async for event in run_with_retries(
				start_attempt,
				cancellation=request.cancellation,
				refresh_auth=self._refresh_credentials if self._refresh_auth is not None else None,
				provider=self.provider,
			):
				yield event
		except ModelCancelled:
			yield self.aborted_message()
			yield Usage()
		finally:
			if owns_client:
				await client.aclose()

	async def _response(self, request: ModelRequest, client: httpx.AsyncClient) -> AsyncIterator[AnyEvent]:
		"""One provider attempt. Headers are rebuilt here so a refreshed token is used."""
		if request.cancellation is not None and request.cancellation.is_set():
			raise ModelCancelled
		url = f"{self._api_base.rstrip('/')}/codex/responses"
		stream_context = client.stream(
			"POST", url, json=self._payload(request), headers=self._request_headers()
		)
		response: httpx.Response | None = None
		try:
			response = await await_with_cancellation(stream_context.__aenter__(), request.cancellation)
			assert response is not None
			if response.status_code >= 400:
				body = await await_with_cancellation(response.aread(), request.cancellation)
				raise provider_error_from_http(
					status_code=response.status_code,
					provider=self.provider,
					body=body,
					headers=response.headers,
				)
			assembler = _ResponseAssembler(
				emit_deltas=request.stream,
				tool_display_templates=request.tool_display_templates,
			)
			try:
				async for raw in iterate_with_cancellation(_iter_sse(response), request.cancellation):
					if raw.get("type") in {"error", "response.failed"}:
						detail = provider_error_detail(raw) or "OpenAI Codex returned an error"
						raise normalize_provider_error(RuntimeError(detail), provider=self.provider)
					for event in assembler.add_event(raw):
						yield event
					if assembler.finished:
						break
			except ModelCancelled:
				assembler.stop_reason = "aborted"  # an aborted turn keeps its partial content
			yield assembler.assistant_message(self)
			yield assembler.usage
		except httpx.HTTPError as exc:
			raise normalize_provider_error(exc, provider=self.provider) from exc
		finally:
			if response is not None:
				await stream_context.__aexit__(*sys.exc_info())

	async def _refresh_credentials(self) -> None:
		"""`run_with_retries` refresh hook: swap in fresh runtime auth after a rejection."""
		assert self._refresh_auth is not None
		auth = await self._refresh_auth(self._api_key)
		self._api_key = auth.token
		self._api_base = auth.base_url or self._api_base
		self._headers = {**self._headers, **auth.headers}

	def _payload(self, request: ModelRequest) -> dict[str, Any]:
		payload: dict[str, Any] = {
			"model": self._remote_model,
			"store": False,
			"stream": True,
			"instructions": request.system_prompt,
			"input": _responses_input(
				request.messages,
				self,
				resolve_attachment=request.resolve_attachment,
			),
			"text": {"verbosity": "low"},
			"include": ["reasoning.encrypted_content"],
			# codex reasons even without an effort setting; without this the summary
			# text never streams and thinking blocks come back empty
			"reasoning": {"summary": "auto"},
			"tool_choice": "auto",
			"parallel_tool_calls": True,
			**self._params,
			**(request.params or {}),
		}
		if request.tools:
			payload["tools"] = [_responses_tool(tool) for tool in request.tools]
		return payload

	def _request_headers(self) -> dict[str, str]:
		return {
			**self._headers,
			"Authorization": f"Bearer {self._api_key}",
			"OpenAI-Beta": "responses=experimental",
			"accept": "text/event-stream",
			"content-type": "application/json",
		}

	def _model_catalog_headers(self) -> dict[str, str]:
		headers = self._request_headers()
		headers["accept"] = "application/json"
		headers.pop("content-type", None)
		return headers


def codex_client_version() -> str:
	"""Version the Codex catalog filters models by: the env override, else the far-future default."""
	return os.environ.get("FLOW_CODEX_CLIENT_VERSION") or DEFAULT_CODEX_CLIENT_VERSION


def static_context_window(model: str) -> int | None:
	"""Best-known context window without network or auth (the fallback table)."""
	return _fallback_model_limits(model).context_window


def _fallback_model_limits(model: str) -> _CodexModelLimits:
	for model_id, context_window_tokens in _CODEX_FALLBACK_CONTEXT_WINDOWS.items():
		if model == model_id or model.startswith(f"{model_id}-20"):
			return _CodexModelLimits(
				context_window=context_window_tokens,
				max_output_tokens=DEFAULT_CODEX_MAX_OUTPUT_TOKENS,
				auto_compact_threshold_tokens=(context_window_tokens * DEFAULT_AUTO_COMPACT_PERCENT // 100),
			)
	return _CodexModelLimits()


def _catalog_model_limits(payload: object, model: str) -> _CodexModelLimits | None:
	if not isinstance(payload, Mapping):
		return None
	models = payload.get("models")
	if not isinstance(models, list):
		return None
	for item in models:
		if not isinstance(item, Mapping) or item.get("slug") != model:
			continue
		context_window_tokens = _positive_int(item.get("context_window")) or _positive_int(
			item.get("max_context_window")
		)
		if context_window_tokens is None:
			return None
		effective_percent = _positive_int(item.get("effective_context_window_percent")) or 100
		if effective_percent > 100:
			return None
		effective_context_window_tokens = max(1, context_window_tokens * effective_percent // 100)
		auto_compact_threshold_tokens = _positive_int(item.get("auto_compact_token_limit"))
		if auto_compact_threshold_tokens is None:
			auto_compact_threshold_tokens = context_window_tokens * DEFAULT_AUTO_COMPACT_PERCENT // 100
		return _CodexModelLimits(
			context_window=context_window_tokens,
			max_output_tokens=_positive_int(item.get("max_output_tokens")),
			auto_compact_threshold_tokens=min(auto_compact_threshold_tokens, effective_context_window_tokens),
		)
	return None


def _merge_model_limits(discovered: _CodexModelLimits, fallback: _CodexModelLimits) -> _CodexModelLimits:
	return _CodexModelLimits(
		context_window=discovered.context_window or fallback.context_window,
		max_output_tokens=discovered.max_output_tokens or fallback.max_output_tokens,
		auto_compact_threshold_tokens=(
			discovered.auto_compact_threshold_tokens or fallback.auto_compact_threshold_tokens
		),
	)


def _positive_int(value: object) -> int | None:
	if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
		return None
	return value


# --- response assembly -----------------------------------------------------


class _ToolCallBuilder:
	"""One function call's identity and its streamed argument fragments."""

	def __init__(self, item: Mapping[str, Any]):
		self.item_id = _string(item.get("id"))
		self.call_id = _string(item.get("call_id")) or "call_0"
		self.name = _string(item.get("name"))
		self.arguments = _string(item.get("arguments"))

	def build(self) -> ToolCall:
		state = {"item_id": self.item_id} if self.item_id else None
		try:
			parsed = json.loads(self.arguments or "{}")
		except ValueError:
			error = f"Invalid JSON in arguments for {self.name!r}; resend the call with valid JSON."
			return ToolCall(id=self.call_id, name=self.name, arguments={}, error=error, provider_state=state)
		if not isinstance(parsed, dict):
			error = f"Arguments for {self.name!r} must be a JSON object."
			return ToolCall(id=self.call_id, name=self.name, arguments={}, error=error, provider_state=state)
		return ToolCall(
			id=self.call_id,
			name=self.name,
			arguments=parsed,
			provider_state=state,
		)


@dataclass(slots=True)
class _ResponseAssembler:
	"""Assembles one Responses SSE stream into ordered content blocks.

	Blocks are keyed by the item id events reference them with; a tool call sits in
	`content` as its builder until the final assembly parses its arguments once.
	"""

	emit_deltas: bool
	tool_display_templates: Mapping[str, str] = field(default_factory=dict)
	content: list[TextContent | ThinkingContent | _ToolCallBuilder] = field(default_factory=list)
	positions: dict[str, int] = field(default_factory=dict)
	calls: dict[str, _ToolCallBuilder] = field(default_factory=dict)  # by item id and call id
	ready_calls: set[str] = field(default_factory=set)
	reasoning_part_keys: dict[str, tuple[str, int]] = field(default_factory=dict)
	usage: Usage = field(default_factory=Usage)
	response_id: str | None = None
	response_model: str | None = None
	stop_reason: StopReason = "stop"
	finished: bool = False

	def add_event(self, raw: Mapping[str, Any]) -> list[AnyEvent]:
		"""Fold one SSE event into the assembly; return the live deltas it produced."""
		kind = raw.get("type")
		item = raw.get("item")
		if kind == "response.output_item.added" and isinstance(item, Mapping):
			return self._open_item(item)
		if kind == "response.function_call_arguments.delta":
			call = _find_call(self.calls, raw.get("item_id"), raw.get("call_id"))
			if call is not None and isinstance(raw.get("delta"), str):
				call.arguments += raw["delta"]
				return self._ready_event(call)
		elif kind == "response.function_call_arguments.done":
			call = _find_call(self.calls, raw.get("item_id"), raw.get("call_id"))
			if call is not None and isinstance(raw.get("arguments"), str):
				call.arguments = raw["arguments"]
				return self._ready_event(call, allow_empty=True)
		elif kind in {"response.reasoning_summary_text.delta", "response.reasoning_text.delta"}:
			return self._append_thinking(raw)
		elif kind == "response.output_text.delta":
			return self._append_text(raw)
		elif kind in {"response.output_item.done", "response.output_item.completed"}:
			if isinstance(item, Mapping):
				return self._close_item(item)
		elif kind in {"response.completed", "response.done", "response.incomplete"}:
			self._finish(raw, truncated=kind == "response.incomplete")
			return self._ready_events(allow_empty=True)
		return []

	def _open_item(self, item: Mapping[str, Any]) -> list[AnyEvent]:
		item_type = item.get("type")
		if item_type == "reasoning":
			self._place(
				_string(item.get("id")),
				ThinkingContent(thinking=_reasoning_text(item), provider_state={"item": dict(item)}),
			)
		elif item_type == "message":
			self._place(
				_string(item.get("id")),
				TextContent(text=_message_text(item), provider_state=_message_state(item)),
			)
		elif item_type == "function_call":
			call = _ToolCallBuilder(item)
			self._register(call)
			self.content.append(call)
			events: list[AnyEvent] = []
			if self.emit_deltas:
				events.append(ToolCallStarted(id=call.call_id, name=call.name))
			events.extend(self._ready_event(call))
			return events
		return []

	def _close_item(self, item: Mapping[str, Any]) -> list[AnyEvent]:
		item_type = item.get("type")
		if item_type == "reasoning":
			item_id = _string(item.get("id"))
			streamed = self._block_at(item_id, ThinkingContent)
			sealed = ThinkingContent(
				# the done item omits summary text when it was only streamed
				thinking=_reasoning_text(item) or (streamed.thinking if streamed else ""),
				provider_state={"item": dict(item)},
			)
			if streamed is None:
				self._place(item_id, sealed)
			else:
				self.content[self.positions[item_id]] = sealed
		elif item_type == "function_call":
			call = _find_call(self.calls, item.get("id"), item.get("call_id"))
			if call is None:
				call = _ToolCallBuilder(item)
				self._register(call)
				self.content.append(call)
			if isinstance(item.get("arguments"), str):
				call.arguments = item["arguments"]
			return self._ready_event(call, allow_empty=True)
		elif item_type == "message":
			return self._close_message(item)
		return []

	def _ready_event(self, call: _ToolCallBuilder, *, allow_empty: bool = False) -> list[AnyEvent]:
		if not self.emit_deltas or call.call_id in self.ready_calls:
			return []
		event = tool_call_display_ready_event(
			call.call_id,
			call.name,
			call.arguments,
			display_template=self.tool_display_templates.get(call.name),
			complete=allow_empty,
		)
		if event is None:
			return []
		self.ready_calls.add(call.call_id)
		return [event]

	def _ready_events(self, *, allow_empty: bool = False) -> list[AnyEvent]:
		events: list[AnyEvent] = []
		for block in self.content:
			if isinstance(block, _ToolCallBuilder):
				events.extend(self._ready_event(block, allow_empty=allow_empty))
		return events

	def _close_message(self, item: Mapping[str, Any]) -> list[AnyEvent]:
		item_id = _string(item.get("id"))
		text = _message_text(item)
		block = self._block_at(item_id, TextContent)
		if block is None:
			if text:
				self._place(item_id, TextContent(text=text, provider_state=_message_state(item)))
			return []
		block.provider_state = _message_state(item) or block.provider_state
		if text and not block.text:
			block.text = text
			if self.emit_deltas:
				return [TextDelta(text=text)]
		return []

	def _append_thinking(self, raw: Mapping[str, Any]) -> list[AnyEvent]:
		delta = raw.get("delta")
		if not isinstance(delta, str) or not delta:
			return []
		item_id = _string(raw.get("item_id"))
		block = self._block_at(item_id, ThinkingContent)
		if block is None:
			block = ThinkingContent(thinking="")
			self._place(item_id, block)
		part_key = _reasoning_part_key(raw)
		previous = self.reasoning_part_keys.get(item_id)
		separator = (
			"\n\n"
			if part_key is not None and previous is not None and part_key != previous and block.thinking
			else ""
		)
		if part_key is not None:
			self.reasoning_part_keys[item_id] = part_key
		text = separator + delta
		block.thinking += text
		return [ThinkingDelta(thinking=text)] if self.emit_deltas else []

	def _append_text(self, raw: Mapping[str, Any]) -> list[AnyEvent]:
		delta = raw.get("delta")
		if not isinstance(delta, str) or not delta:
			return []
		item_id = _string(raw.get("item_id"))
		block = self._block_at(item_id, TextContent)
		if block is None:
			block = TextContent(text="", provider_state={"id": item_id} if item_id else None)
			self._place(item_id, block)
		block.text += delta
		return [TextDelta(text=delta)] if self.emit_deltas else []

	def _finish(self, raw: Mapping[str, Any], *, truncated: bool) -> None:
		response = raw.get("response")
		if isinstance(response, Mapping):
			usage = response.get("usage")
			if isinstance(usage, Mapping):
				details = usage.get("input_tokens_details")
				self.usage = Usage(
					input_tokens=_integer(usage.get("input_tokens")),
					output_tokens=_integer(usage.get("output_tokens")),
					cache_read_tokens=_integer(details.get("cached_tokens"))
					if isinstance(details, Mapping)
					else 0,
				)
			self.response_id = _string(response.get("id")) or None
			self.response_model = _string(response.get("model")) or None
		self.stop_reason = "length" if truncated else "stop"
		self.finished = True

	def assistant_message(self, model: CodexModel) -> AssistantMessage:
		content = [block.build() if isinstance(block, _ToolCallBuilder) else block for block in self.content]
		has_calls = any(isinstance(block, ToolCall) for block in content)
		actual = self.response_model
		message = AssistantMessage(
			content=content,
			api=model.api,
			provider=model.provider,
			model=model.model,
			response_model=actual if actual and actual != model._remote_model else None,
			response_id=self.response_id,
			# only a plain stop upgrades: an incomplete response keeps "length" so its
			# possibly-truncated calls are never executed
			stop_reason="tool_use" if has_calls and self.stop_reason == "stop" else self.stop_reason,
		)
		return with_tool_call_displays(message, self.tool_display_templates)

	def _place(self, item_id: str, block: TextContent | ThinkingContent) -> None:
		self.positions[item_id] = len(self.content)
		self.content.append(block)

	def _register(self, call: _ToolCallBuilder) -> None:
		for key in (call.item_id, call.call_id):
			if key:
				self.calls[key] = call

	def _block_at[B: (TextContent, ThinkingContent)](self, item_id: str, block_type: type[B]) -> B | None:
		position = self.positions.get(item_id)
		if position is None:
			return None
		block = self.content[position]
		return block if isinstance(block, block_type) else None


def _find_call(calls: dict[str, _ToolCallBuilder], *candidates: Any) -> _ToolCallBuilder | None:
	"""Match a call by any id the event carries; a lone call needs no id at all."""
	for value in candidates:
		if isinstance(value, str) and value in calls:
			return calls[value]
	unique = {id(call): call for call in calls.values()}
	return next(iter(unique.values())) if len(unique) == 1 else None


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


# --- transcript -> Responses input ----------------------------------------


def _responses_input(
	messages: list[TranscriptMessage],
	model: CodexModel,
	*,
	resolve_attachment: Callable[[str], bytes] | None = None,
) -> list[dict]:
	items: list[dict] = []
	text_index = 0
	dropped_calls: set[str] = set()
	supports_images = model.supports_images
	for message in messages:
		if isinstance(message, UserMessage):
			text, images = resolve_user_content(
				message,
				resolve_attachment=resolve_attachment,
				supports_images=supports_images,
			)
			content = []
			if text:
				content.append({"type": "input_text", "text": text})
			content.extend({"type": "input_image", "image_url": image.data_url} for image in images)
			items.append({"role": "user", "content": content})
		elif isinstance(message, AssistantMessage):
			if message.stop_reason in {"error", "aborted"}:
				# drop this turn's results too: an answer without its call is rejected
				dropped_calls.update(call.id for call in message.tool_calls)
				continue
			same_model = (
				message.api == model.api
				and message.provider == model.provider
				and message.model == model.model
			)
			for block in message.content:
				if isinstance(block, ThinkingContent):
					reasoning_item = _stored_reasoning_item(block) if same_model else None
					if reasoning_item is not None:
						items.append(reasoning_item)
					elif not block.redacted and block.thinking:
						# deliberately degrades cross-model thinking to ordinary text
						items.append(_assistant_text_item(block.thinking, f"msg_{text_index}"))
						text_index += 1
				elif isinstance(block, TextContent):
					item_id, phase = _message_identity(block.provider_state) if same_model else (None, None)
					items.append(_assistant_text_item(block.text, item_id or f"msg_{text_index}", phase))
					text_index += 1
				elif isinstance(block, ToolCall):
					items.append(_function_call_item(block))
		elif isinstance(message, ToolResult):
			if message.tool_call_id in dropped_calls:
				continue
			images = resolve_tool_images(
				message, resolve_attachment=resolve_attachment, supports_images=supports_images
			)
			output: str | list[dict] = message.content
			if images:
				# the Responses API takes image parts inside the tool output itself
				output = [
					{"type": "input_text", "text": message.content},
					*({"type": "input_image", "image_url": image.data_url} for image in images),
				]
			items.append(
				{
					"type": "function_call_output",
					"call_id": message.tool_call_id,
					"output": output,
				}
			)
	return items


def _stored_reasoning_item(block: ThinkingContent) -> dict | None:
	"""The raw reasoning item this block was streamed as, if we stored one."""
	state = block.provider_state
	item = state.get("item") if isinstance(state, dict) else None
	return item if isinstance(item, dict) else None


def _message_identity(state: dict | None) -> tuple[str | None, str | None]:
	"""The (item id, phase) a text block was streamed with, if we stored them."""
	if not isinstance(state, dict):
		return None, None
	item_id = state.get("id")
	if not isinstance(item_id, str) or not item_id:
		return None, None
	phase = state.get("phase")
	return item_id, phase if isinstance(phase, str) else None


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


def _function_call_item(call: ToolCall) -> dict:
	item = {
		"type": "function_call",
		"call_id": call.id,
		"name": call.name,
		"arguments": json.dumps(call.arguments),
	}
	state = call.provider_state
	item_id = state.get("item_id") if isinstance(state, dict) else None
	if isinstance(item_id, str) and item_id:
		item["id"] = item_id
	return item


def _responses_tool(tool: dict[str, Any]) -> dict:
	function = tool.get("function") or {}
	return {
		"type": "function",
		"name": function.get("name") or "",
		"description": function.get("description") or "",
		"parameters": function.get("parameters") or {},
		"strict": None,
	}


# --- wire readers ----------------------------------------------------------


def _message_state(item: Mapping[str, Any]) -> dict | None:
	"""The identity a message must replay with: its item id, plus the phase Codex
	attaches to commentary vs final answers."""
	item_id = _string(item.get("id"))
	if not item_id:
		return None
	phase = item.get("phase")
	if isinstance(phase, str) and phase in {"commentary", "final_answer"}:
		return {"id": item_id, "phase": phase}
	return {"id": item_id}


def _reasoning_text(item: Mapping[str, Any]) -> str:
	"""Summary text when the model summarises, else the raw reasoning text."""
	for key in ("summary", "content"):
		parts = item.get(key)
		if not isinstance(parts, list):
			continue
		text = "\n\n".join(
			part.get("text", "")
			for part in parts
			if isinstance(part, Mapping) and isinstance(part.get("text"), str) and part.get("text")
		)
		if text:
			return text
	return ""


def _reasoning_part_key(raw: Mapping[str, Any]) -> tuple[str, int] | None:
	"""Identity of one streamed reasoning part, when the provider supplies it."""
	kind = raw.get("type")
	index_field = "summary_index" if kind == "response.reasoning_summary_text.delta" else "content_index"
	index = raw.get(index_field)
	return (index_field, index) if isinstance(index, int) and not isinstance(index, bool) else None


def _message_text(item: Mapping[str, Any]) -> str:
	parts = item.get("content")
	if not isinstance(parts, list):
		return ""
	return "".join(
		part.get("text", "")
		for part in parts
		if isinstance(part, Mapping) and part.get("type") == "output_text"
	)


def _json_object(value: str) -> dict:
	try:
		parsed = json.loads(value)
	except json.JSONDecodeError:
		return {}
	return parsed if isinstance(parsed, dict) else {}


def _string(value: Any) -> str:
	return value if isinstance(value, str) else ""


def _integer(value: Any) -> int:
	return value if isinstance(value, int) and not isinstance(value, bool) else 0
