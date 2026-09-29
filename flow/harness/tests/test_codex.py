"""The Codex provider: OAuth login machinery, the Responses SSE wire (with
provider-native identities in `provider_state`), and in-adapter retries/refresh."""

import asyncio
import base64
import json

import httpx
import pytest

from flow_harness.events import (
	AssistantMessage,
	DisplaySegment,
	TextContent,
	ThinkingContent,
	ToolCall,
	ToolResult,
	UserMessage,
)
from flow_harness.model import ModelRequest, ProviderError
from flow_harness.model.auth import AuthError, RuntimeAuth, get_auth_provider
from flow_harness.model.credentials import OAuthCredential
from flow_harness.model.providers.codex import (
	CLIENT_ID,
	DEFAULT_CODEX_CLIENT_VERSION,
	CodexModel,
	_responses_input,
	codex_client_version,
)


def _jwt(payload: dict) -> str:
	def seg(obj):
		raw = json.dumps(obj).encode()
		return base64.urlsafe_b64encode(raw).decode().rstrip("=")

	return f"{seg({'alg': 'none'})}.{seg(payload)}.sig"


def _mock_client(handler):
	return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _collect(
	model,
	messages,
	tools=None,
	*,
	system_prompt="",
	stream=True,
	cancellation=None,
	max_output_tokens=None,
	tool_display_templates=None,
):
	return [
		event
		async for event in model.run(
			ModelRequest(
				messages=messages,
				tools=tools,
				system_prompt=system_prompt,
				stream=stream,
				cancellation=cancellation,
				max_output_tokens=max_output_tokens,
				tool_display_templates=tool_display_templates or {},
			)
		)
	]


def _success_sse(text="ok"):
	return "\n\n".join(
		[
			f'data: {{"type":"response.output_text.delta","delta":"{text}"}}',
			'data: {"type":"response.completed","response":{}}',
		]
	)


# --- OAuth provider --------------------------------------------------------


def test_authorize_url():
	url = get_auth_provider("codex").authorize_url(challenge="CH", state="ST")
	assert url.startswith("https://auth.openai.com/oauth/authorize?")
	for fragment in (
		f"client_id={CLIENT_ID}",
		"code_challenge=CH",
		"code_challenge_method=S256",
		"state=ST",
		"id_token_add_organizations=true",
	):
		assert fragment in url


async def test_exchange_builds_credential():
	captured = {}

	def handler(request):
		captured["body"] = request.content.decode()
		return httpx.Response(
			200,
			json={
				"access_token": _jwt({"chatgpt_account_id": "acc-1"}),
				"refresh_token": "refresh-1",
				"expires_in": 3600,
			},
		)

	async with _mock_client(handler) as client:
		cred = await get_auth_provider("codex").exchange(
			"the-code", "the-verifier", client=client, now_ms=1_000
		)

	assert "grant_type=authorization_code" in captured["body"]
	assert "code=the-code" in captured["body"]
	assert "code_verifier=the-verifier" in captured["body"]
	assert cred.refresh == "refresh-1"
	assert cred.account_id == "acc-1"
	assert cred.expires == 1_000 + 3600 * 1000


async def test_refresh_keeps_old_refresh_token_when_absent():
	def handler(request):
		assert "grant_type=refresh_token" in request.content.decode()
		return httpx.Response(200, json={"access_token": _jwt({}), "expires_in": 100})

	old = OAuthCredential(access="old", refresh="keep-me", expires=0, account_id="acc")
	async with _mock_client(handler) as client:
		cred = await get_auth_provider("codex").refresh(old, client=client, now_ms=0)
	assert cred.refresh == "keep-me"


def test_runtime_auth_headers():
	auth = get_auth_provider("codex").runtime_auth(
		OAuthCredential(access="tok", refresh="r", expires=0, account_id="acc-9")
	)
	assert auth.token == "tok"
	assert auth.base_url == "https://chatgpt.com/backend-api"
	assert auth.headers["chatgpt-account-id"] == "acc-9"
	assert auth.headers["originator"] == "flow"


def test_runtime_auth_requires_account_id():
	with pytest.raises(AuthError, match="account id"):
		get_auth_provider("codex").runtime_auth(OAuthCredential(access="tok", refresh="r", expires=1))


def test_codex_subscription_limits_have_a_conservative_fallback():
	model = CodexModel("codex/gpt-5.6-sol", api_key="token")

	assert model.context_window == 272_000
	assert model.max_output_tokens == 128_000
	assert model.auto_compact_threshold_tokens == 244_800


async def test_loads_and_caches_account_model_limits(monkeypatch):
	monkeypatch.setenv("FLOW_CODEX_CLIENT_VERSION", "9.9.9")
	requests = []

	def handler(request):
		requests.append(request)
		return httpx.Response(
			200,
			json={
				"models": [
					{
						"slug": "gpt-5.6-sol",
						"max_context_window": 1_050_000,
						"effective_context_window_percent": 88,
						"auto_compact_token_limit": 900_000,
						"max_output_tokens": 128_000,
					}
				]
			},
		)

	async with _mock_client(handler) as client:
		model = CodexModel(
			"codex/gpt-5.6-sol",
			api_key="token",
			api_base="https://example.test/backend-api",
			headers={"chatgpt-account-id": "acc"},
			client=client,
		)
		await model.load_model_limits()
		await model.load_model_limits()

	assert len(requests) == 1
	request = requests[0]
	assert str(request.url) == "https://example.test/backend-api/codex/models?client_version=9.9.9"
	assert request.headers["authorization"] == "Bearer token"
	assert request.headers["chatgpt-account-id"] == "acc"
	assert model.context_window == 1_050_000
	assert model.max_output_tokens == 128_000
	assert model.auto_compact_threshold_tokens == 900_000


@pytest.fixture
def uncached_client_version(monkeypatch):
	monkeypatch.delenv("FLOW_CODEX_CLIENT_VERSION", raising=False)
	monkeypatch.setattr("flow_harness.model.providers.codex._latest_client_version", None)


async def test_client_version_override_skips_npm(monkeypatch):
	monkeypatch.setenv("FLOW_CODEX_CLIENT_VERSION", "1.2.3")

	def handler(request):
		raise AssertionError("an override needs no lookup")

	async with _mock_client(handler) as client:
		assert await codex_client_version(client) == "1.2.3"


async def test_client_version_is_the_latest_npm_release_looked_up_once(uncached_client_version):
	urls = []

	def handler(request):
		urls.append(str(request.url))
		return httpx.Response(200, json={"version": "0.200.0"})

	async with _mock_client(handler) as client:
		assert await codex_client_version(client) == "0.200.0"
		assert await codex_client_version(client) == "0.200.0"

	assert urls == ["https://registry.npmjs.org/@openai/codex/latest"]


@pytest.mark.parametrize(
	"reply", [httpx.Response(503), httpx.Response(200, json={"version": "latest"})], ids=["down", "junk"]
)
async def test_client_version_falls_back_to_the_pin(uncached_client_version, reply):
	async with _mock_client(lambda request: reply) as client:
		assert await codex_client_version(client) == DEFAULT_CODEX_CLIENT_VERSION


# --- streaming wire --------------------------------------------------------


async def test_streams_text_tools_and_usage():
	captured = {}
	sse = "\n\n".join(
		[
			(
				'data: {"type":"response.output_item.added","item":'
				'{"type":"message","id":"msg_1","content":[]}}'
			),
			'data: {"type":"response.output_text.delta","item_id":"msg_1","delta":"hello "}',
			(
				'data: {"type":"response.output_item.done","item":'
				'{"type":"message","id":"msg_1","phase":"commentary","content":'
				'[{"type":"output_text","text":"hello "}]}}'
			),
			(
				'data: {"type":"response.output_item.done","item":'
				'{"type":"reasoning","id":"reason_1","encrypted_content":"opaque"}}'
			),
			(
				'data: {"type":"response.output_item.added","item":'
				'{"type":"function_call","id":"item_1","call_id":"call_1","name":"bash"}}'
			),
			(
				'data: {"type":"response.function_call_arguments.delta",'
				'"item_id":"item_1","delta":"{\\"command\\":\\"pwd\\"}"}'
			),
			(
				'data: {"type":"response.output_item.done","item":'
				'{"type":"function_call","id":"item_1","call_id":"call_1",'
				'"name":"bash","arguments":"{\\"command\\":\\"pwd\\"}"}}'
			),
			(
				'data: {"type":"response.completed","response":{"id":"resp_1",'
				'"model":"gpt-concrete","usage":'
				'{"input_tokens":12,"output_tokens":4,'
				'"input_tokens_details":{"cached_tokens":9}}}}'
			),
			"data: [DONE]",
		]
	)

	def handler(request):
		captured["url"] = str(request.url)
		captured["headers"] = dict(request.headers)
		captured["payload"] = json.loads(request.content)
		return httpx.Response(200, text=sse)

	async with _mock_client(handler) as client:
		model = CodexModel(
			"codex/gpt-test",
			api_key="oauth-token",
			api_base="https://example.test/backend-api",
			headers={"chatgpt-account-id": "acc", "Authorization": "must-not-win"},
			client=client,
		)
		events = await _collect(
			model,
			[UserMessage(content="hi")],
			[
				{
					"type": "function",
					"function": {
						"name": "bash",
						"description": "run",
						"parameters": {"type": "object"},
					},
				}
			],
			system_prompt="be useful",
			max_output_tokens=12_345,
			tool_display_templates={"bash": "Running {{ command }}"},
		)

	assert captured["url"] == "https://example.test/backend-api/codex/responses"
	assert captured["headers"]["authorization"] == "Bearer oauth-token"
	assert captured["payload"]["model"] == "gpt-test"
	assert captured["payload"]["instructions"] == "be useful"
	assert captured["payload"]["tools"][0]["name"] == "bash"
	assert "max_output_tokens" not in captured["payload"]
	assert captured["payload"]["reasoning"] == {"summary": "auto"}
	assert [event.type for event in events] == [
		"text_delta",
		"tool_call_started",
		"tool_call_display_ready",
		"assistant_message",
		"usage",
	]
	assert events[2].arguments == {"command": "pwd"}
	assert events[2].display == [
		DisplaySegment(text="Running "),
		DisplaySegment(text="pwd", arg="command"),
	]
	message = events[-2]
	assert message.text == "hello "
	assert [block.type for block in message.content] == ["text", "thinking", "tool_call"]
	assert message.content[0].provider_state == {"id": "msg_1", "phase": "commentary"}
	thinking = message.content[1]
	assert isinstance(thinking, ThinkingContent)
	assert thinking.provider_state["item"]["encrypted_content"] == "opaque"
	assert thinking.thinking_signature is None
	call = message.tool_calls[0]
	assert call.id == "call_1"  # the plain provider call id, usable by ToolResult as-is
	assert call.provider_state == {"item_id": "item_1"}
	assert call.args == {"command": "pwd"}
	assert call.display == [
		DisplaySegment(text="Running "),
		DisplaySegment(text="pwd", arg="command"),
	]
	assert message.api == "openai-codex-responses"
	assert message.provider == "codex"
	assert message.model == "codex/gpt-test"
	assert message.response_model == "gpt-concrete"
	assert message.response_id == "resp_1"
	assert message.stop_reason == "tool_use"
	assert events[-1].input_tokens == 12
	assert events[-1].output_tokens == 4
	assert events[-1].cache_read_tokens == 9


async def test_parallel_tool_calls_are_not_duplicated_by_their_done_items():
	sse = "\n\n".join(
		[
			(
				'data: {"type":"response.output_item.added","item":'
				'{"type":"function_call","id":"item_1","call_id":"call_1","name":"bash"}}'
			),
			(
				'data: {"type":"response.output_item.added","item":'
				'{"type":"function_call","id":"item_2","call_id":"call_2","name":"read"}}'
			),
			(
				'data: {"type":"response.output_item.done","item":'
				'{"type":"function_call","id":"item_1","call_id":"call_1",'
				'"name":"bash","arguments":"{\\"command\\":\\"pwd\\"}"}}'
			),
			(
				'data: {"type":"response.output_item.done","item":'
				'{"type":"function_call","id":"item_2","call_id":"call_2",'
				'"name":"read","arguments":"{\\"path\\":\\"a.txt\\"}"}}'
			),
			'data: {"type":"response.completed","response":{}}',
		]
	)

	async with _mock_client(lambda _r: httpx.Response(200, text=sse)) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		events = await _collect(model, [UserMessage(content="hi")])

	calls = events[-2].tool_calls
	assert [(call.id, call.name) for call in calls] == [("call_1", "bash"), ("call_2", "read")]
	assert calls[0].args == {"command": "pwd"}
	assert calls[1].args == {"path": "a.txt"}


async def test_incomplete_response_keeps_length_over_tool_use():
	sse = "\n\n".join(
		[
			(
				'data: {"type":"response.output_item.done","item":'
				'{"type":"function_call","id":"item_1","call_id":"call_1",'
				'"name":"bash","arguments":"{\\"command\\":\\"pwd\\"}"}}'
			),
			'data: {"type":"response.incomplete","response":{"id":"resp_1","usage":{}}}',
			"data: [DONE]",
		]
	)

	async with _mock_client(lambda _r: httpx.Response(200, text=sse)) as client:
		model = CodexModel("codex/gpt-test", api_key="t", api_base="https://e.test", client=client)
		events = await _collect(model, [UserMessage(content="hi")])

	assert events[-2].tool_calls  # the truncated call is still reported
	assert events[-2].stop_reason == "length"


async def test_non_streaming_suppresses_live_deltas():
	sse = "\n\n".join(
		[
			'data: {"type":"response.output_text.delta","delta":"done"}',
			'data: {"type":"response.completed","response":{}}',
		]
	)

	async with _mock_client(lambda _r: httpx.Response(200, text=sse)) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		events = await _collect(model, [UserMessage(content="hi")], stream=False)

	assert [event.type for event in events] == ["assistant_message", "usage"]
	assert events[0].text == "done"


async def test_streams_reasoning_summary_deltas():
	sse = "\n\n".join(
		[
			(
				'data: {"type":"response.output_item.added","item":'
				'{"type":"reasoning","id":"reason_1","summary":[]}}'
			),
			'data: {"type":"response.reasoning_summary_text.delta","item_id":"reason_1","delta":"weigh "}',
			'data: {"type":"response.reasoning_summary_text.delta","item_id":"reason_1","delta":"options"}',
			(
				'data: {"type":"response.output_item.done","item":'
				'{"type":"reasoning","id":"reason_1","encrypted_content":"opaque",'
				'"summary":[{"type":"summary_text","text":"weigh options"}]}}'
			),
			'data: {"type":"response.completed","response":{}}',
		]
	)

	async with _mock_client(lambda _r: httpx.Response(200, text=sse)) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		events = await _collect(model, [UserMessage(content="hi")])

	assert [event.type for event in events] == [
		"thinking_delta",
		"thinking_delta",
		"assistant_message",
		"usage",
	]
	assert [event.thinking for event in events[:2]] == ["weigh ", "options"]
	thinking = events[-2].content[0]
	assert isinstance(thinking, ThinkingContent)
	assert thinking.thinking == "weigh options"
	assert thinking.provider_state["item"]["encrypted_content"] == "opaque"


async def test_preserves_boundaries_between_reasoning_summary_parts():
	sse = "\n\n".join(
		[
			(
				'data: {"type":"response.output_item.added","item":'
				'{"type":"reasoning","id":"reason_1","summary":[]}}'
			),
			(
				'data: {"type":"response.reasoning_summary_text.delta","item_id":"reason_1",'
				'"summary_index":0,"delta":"**Planning detailed single-file inspections**"}'
			),
			(
				'data: {"type":"response.reasoning_summary_text.delta","item_id":"reason_1",'
				'"summary_index":1,"delta":"**Starting sequential inspection phase**"}'
			),
			(
				'data: {"type":"response.output_item.done","item":'
				'{"type":"reasoning","id":"reason_1","summary":['
				'{"type":"summary_text","text":"**Planning detailed single-file inspections**"},'
				'{"type":"summary_text","text":"**Starting sequential inspection phase**"}]}}'
			),
			'data: {"type":"response.completed","response":{}}',
		]
	)

	async with _mock_client(lambda _r: httpx.Response(200, text=sse)) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		events = await _collect(model, [UserMessage(content="hi")])

	assert [event.thinking for event in events[:2]] == [
		"**Planning detailed single-file inspections**",
		"\n\n**Starting sequential inspection phase**",
	]
	thinking = events[-2].content[0]
	assert isinstance(thinking, ThinkingContent)
	assert thinking.thinking == (
		"**Planning detailed single-file inspections**\n\n**Starting sequential inspection phase**"
	)


async def test_keeps_streamed_reasoning_when_the_done_item_omits_it():
	sse = "\n\n".join(
		[
			'data: {"type":"response.reasoning_text.delta","item_id":"reason_1","delta":"raw thought"}',
			(
				'data: {"type":"response.output_item.done","item":'
				'{"type":"reasoning","id":"reason_1","encrypted_content":"opaque"}}'
			),
			'data: {"type":"response.completed","response":{}}',
		]
	)

	async with _mock_client(lambda _r: httpx.Response(200, text=sse)) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		events = await _collect(model, [UserMessage(content="hi")])

	thinking = events[-2].content[0]
	assert isinstance(thinking, ThinkingContent)
	assert thinking.thinking == "raw thought"
	assert thinking.provider_state["item"]["encrypted_content"] == "opaque"


# --- cancellation ----------------------------------------------------------


async def test_cancellation_closes_active_http_stream():
	class BlockingSSE(httpx.AsyncByteStream):
		def __init__(self):
			self.started = asyncio.Event()
			self.closed = asyncio.Event()

		async def __aiter__(self):
			yield b'data: {"type":"response.output_text.delta","delta":"partial"}\n\n'
			self.started.set()
			await asyncio.Event().wait()

		async def aclose(self):
			self.closed.set()

	body = BlockingSSE()
	cancellation = asyncio.Event()
	async with _mock_client(lambda _r: httpx.Response(200, stream=body)) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		task = asyncio.create_task(_collect(model, [UserMessage(content="hi")], cancellation=cancellation))
		await body.started.wait()
		cancellation.set()
		events = await asyncio.wait_for(task, timeout=1)

	assert body.closed.is_set()
	assert [event.type for event in events] == ["text_delta", "assistant_message", "usage"]
	assert events[-2].text == "partial"
	assert events[-2].stop_reason == "aborted"


async def test_cancellation_interrupts_response_header_wait():
	request_started = asyncio.Event()
	request_cancelled = asyncio.Event()

	async def handler(request):
		request_started.set()
		try:
			await asyncio.Event().wait()
		finally:
			request_cancelled.set()

	cancellation = asyncio.Event()
	async with _mock_client(handler) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		task = asyncio.create_task(_collect(model, [UserMessage(content="hi")], cancellation=cancellation))
		await request_started.wait()
		cancellation.set()
		events = await asyncio.wait_for(task, timeout=1)

	assert request_cancelled.is_set()
	assert [event.type for event in events] == ["assistant_message", "usage"]
	assert events[0].stop_reason == "aborted"


async def test_cancellation_interrupts_error_body_read_and_closes_stream():
	class BlockingErrorBody(httpx.AsyncByteStream):
		def __init__(self):
			self.started = asyncio.Event()
			self.closed = asyncio.Event()

		async def __aiter__(self):
			self.started.set()
			await asyncio.Event().wait()
			if False:
				yield b""

		async def aclose(self):
			self.closed.set()

	body = BlockingErrorBody()
	cancellation = asyncio.Event()
	async with _mock_client(lambda _r: httpx.Response(500, stream=body)) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		task = asyncio.create_task(_collect(model, [UserMessage(content="hi")], cancellation=cancellation))
		await body.started.wait()
		cancellation.set()
		events = await asyncio.wait_for(task, timeout=1)

	assert body.closed.is_set()
	assert [event.type for event in events] == ["assistant_message", "usage"]
	assert events[0].stop_reason == "aborted"


# --- retries + refresh inside the adapter ----------------------------------


@pytest.mark.parametrize("status", [429, 500, 503])
async def test_http_transient_failure_retries_in_stream(status):
	attempts = 0

	def handler(request):
		nonlocal attempts
		attempts += 1
		if attempts == 1:
			return httpx.Response(
				status,
				headers={"retry-after": "0"},
				json={"error": {"message": "provider temporarily unavailable"}},
			)
		return httpx.Response(200, text=_success_sse())

	async with _mock_client(handler) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		events = await _collect(model, [UserMessage(content="hi")])

	assert attempts == 2
	retries = [event for event in events if event.type == "retry"]
	assert [(retry.status, retry.attempt) for retry in retries] == [("scheduled", 2), ("started", 2)]
	assert retries[0].delay_seconds == 0.0
	assert [event.type for event in events[-2:]] == ["assistant_message", "usage"]


async def test_timeout_retries_in_stream(monkeypatch):
	monkeypatch.setattr("flow_harness.model.retry._retry_delay_seconds", lambda error, retry_index: 0)
	attempts = 0

	def handler(request):
		nonlocal attempts
		attempts += 1
		if attempts == 1:
			raise httpx.ReadTimeout("provider stalled", request=request)
		return httpx.Response(200, text=_success_sse())

	async with _mock_client(handler) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		events = await _collect(model, [UserMessage(content="hi")])

	assert attempts == 2
	assert [event.kind for event in events if event.type == "retry"] == ["timeout", None]


async def test_in_stream_overload_retries_before_the_terminal_commits():
	attempts = 0
	overloaded = (
		'data: {"type":"error","error":{"type":"service_unavailable_error",'
		'"code":"server_is_overloaded","message":"server overloaded"}}'
	)

	def handler(request):
		nonlocal attempts
		attempts += 1
		return httpx.Response(200, text=overloaded if attempts == 1 else _success_sse())

	async with _mock_client(handler) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		events = await _collect(model, [UserMessage(content="hi")])

	assert attempts == 2
	assert next(event.kind for event in events if event.type == "retry") == "overloaded"
	assert len([event for event in events if event.type == "assistant_message"]) == 1


async def test_invalid_request_does_not_retry():
	attempts = 0

	def handler(request):
		nonlocal attempts
		attempts += 1
		return httpx.Response(400, json={"error": {"message": "invalid tool schema"}})

	async with _mock_client(handler) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		events = []
		with pytest.raises(ProviderError) as raised:
			async for event in model.run(ModelRequest(messages=[UserMessage(content="hi")])):
				events.append(event)

	assert attempts == 1
	assert [event for event in events if event.type == "retry"] == []
	assert raised.value.kind == "invalid_request"


async def test_context_overflow_is_typed_and_not_retried():
	attempts = 0

	def handler(request):
		nonlocal attempts
		attempts += 1
		return httpx.Response(
			400,
			json={
				"error": {
					"code": "context_length_exceeded",
					"message": "Your input exceeds the context window of this model.",
				}
			},
		)

	async with _mock_client(handler) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		with pytest.raises(ProviderError) as raised:
			await _collect(model, [UserMessage(content="hi")])

	assert attempts == 1
	assert raised.value.kind == "context_overflow"


async def test_rejected_token_refreshes_credentials_and_retries():
	auths = []

	def handler(request):
		auths.append(request.headers["authorization"])
		if len(auths) == 1:
			return httpx.Response(401, json={"error": {"message": "The access token expired"}})
		return httpx.Response(200, text=_success_sse())

	async def refresh_auth(rejected_token):
		assert rejected_token == "stale-token"
		return RuntimeAuth(token="fresh-token", headers={"chatgpt-account-id": "acc"})

	async with _mock_client(handler) as client:
		model = CodexModel(
			"codex/gpt-test",
			api_key="stale-token",
			headers={"chatgpt-account-id": "acc"},
			client=client,
			refresh_auth=refresh_auth,
		)
		events = await _collect(model, [UserMessage(content="hi")])

	assert auths == ["Bearer stale-token", "Bearer fresh-token"]
	retries = [event for event in events if event.type == "retry"]
	assert [(retry.status, retry.kind) for retry in retries] == [("scheduled", "auth"), ("started", None)]
	assert retries[0].delay_seconds == 0
	assert [event.text for event in events if event.type == "assistant_message"] == ["ok"]


# --- transcript replay -----------------------------------------------------


def test_replays_opaque_reasoning_before_tool_turn():
	reasoning = {"type": "reasoning", "id": "reason_1", "encrypted_content": "opaque"}
	model = CodexModel("codex/gpt-test", api_key="token")
	items = _responses_input(
		[
			AssistantMessage(
				content=[
					ThinkingContent(thinking="", provider_state={"item": reasoning}),
					ToolCall(
						id="call_1",
						name="bash",
						arguments={},
						provider_state={"item_id": "item_1"},
					),
				],
				api=model.api,
				provider=model.provider,
				model=model.model,
			),
			ToolResult(tool_call_id="call_1", name="bash", content="ok"),
		],
		model,
	)

	assert items[0] == reasoning
	assert items[1]["type"] == "function_call"
	assert items[1]["call_id"] == "call_1"
	assert items[1]["id"] == "item_1"
	assert items[2] == {"type": "function_call_output", "call_id": "call_1", "output": "ok"}


def test_replays_text_item_identity_and_phase_to_the_same_model():
	model = CodexModel("codex/gpt-test", api_key="token")
	items = _responses_input(
		[
			AssistantMessage(
				content=[TextContent(text="working", provider_state={"id": "msg_1", "phase": "commentary"})],
				api=model.api,
				provider=model.provider,
				model=model.model,
			)
		],
		model,
	)

	assert items == [
		{
			"type": "message",
			"role": "assistant",
			"content": [{"type": "output_text", "text": "working", "annotations": []}],
			"status": "completed",
			"id": "msg_1",
			"phase": "commentary",
		}
	]


def test_does_not_replay_reasoning_to_a_different_model():
	reasoning = {"type": "reasoning", "id": "reason_1", "encrypted_content": "opaque"}
	target = CodexModel("codex/gpt-new", api_key="token")
	items = _responses_input(
		[
			AssistantMessage(
				content=[ThinkingContent(thinking="safe summary", provider_state={"item": reasoning})],
				api=target.api,
				provider=target.provider,
				model="codex/gpt-old",
			)
		],
		target,
	)

	assert items == [
		{
			"type": "message",
			"role": "assistant",
			"content": [{"type": "output_text", "text": "safe summary", "annotations": []}],
			"status": "completed",
			"id": "msg_0",
		}
	]


def test_does_not_replay_aborted_assistant_response():
	target = CodexModel("codex/gpt-test", api_key="token")
	aborted = AssistantMessage(
		content="partial",
		api=target.api,
		provider=target.provider,
		model=target.model,
		stop_reason="aborted",
	)

	assert _responses_input([aborted], target) == []


def test_drops_results_answering_a_dropped_assistant_turn():
	target = CodexModel("codex/gpt-test", api_key="token")
	aborted = AssistantMessage(
		content=[ToolCall(id="call_1", name="read", arguments={"path": "a.txt"})],
		api=target.api,
		provider=target.provider,
		model=target.model,
		stop_reason="aborted",
	)
	repair = ToolResult(tool_call_id="call_1", name="read", content="interrupted", is_error=True)

	# the call and its answer must both be dropped
	assert _responses_input([aborted, repair], target) == []
