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


async def test_oauth_login_refresh_and_runtime_auth():
	provider = get_auth_provider("codex")
	url = provider.authorize_url(challenge="CH", state="ST")
	assert url.startswith("https://auth.openai.com/oauth/authorize?")
	for fragment in (
		f"client_id={CLIENT_ID}",
		"code_challenge=CH",
		"code_challenge_method=S256",
		"state=ST",
		"id_token_add_organizations=true",
	):
		assert fragment in url

	bodies = []

	def handler(request):
		bodies.append(request.content.decode())
		if len(bodies) == 1:
			return httpx.Response(
				200,
				json={
					"access_token": _jwt({"chatgpt_account_id": "acc-1"}),
					"refresh_token": "refresh-1",
					"expires_in": 3600,
				},
			)
		return httpx.Response(200, json={"access_token": _jwt({}), "expires_in": 100})

	async with _mock_client(handler) as client:
		cred = await provider.exchange("the-code", "the-verifier", client=client, now_ms=1_000)
		refreshed = await provider.refresh(cred, client=client, now_ms=0)

	assert "grant_type=authorization_code" in bodies[0]
	assert "code=the-code" in bodies[0]
	assert "code_verifier=the-verifier" in bodies[0]
	assert cred.refresh == "refresh-1"
	assert cred.account_id == "acc-1"
	assert cred.expires == 1_000 + 3600 * 1000
	# a refresh response without a refresh token keeps the old one
	assert "grant_type=refresh_token" in bodies[1]
	assert refreshed.refresh == "refresh-1"

	auth = provider.runtime_auth(OAuthCredential(access="tok", refresh="r", expires=0, account_id="acc-9"))
	assert auth.token == "tok"
	assert auth.base_url == "https://chatgpt.com/backend-api"
	assert auth.headers["chatgpt-account-id"] == "acc-9"
	assert auth.headers["originator"] == "flow"
	with pytest.raises(AuthError, match="account id"):
		provider.runtime_auth(OAuthCredential(access="tok", refresh="r", expires=1))


async def test_model_limits_fall_back_until_the_account_catalog_loads_once(monkeypatch):
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
		# conservative subscription fallbacks until the catalog answers
		assert model.context_window == 272_000
		assert model.max_output_tokens == 128_000
		assert model.auto_compact_threshold_tokens == 244_800
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

	monkeypatch.delenv("FLOW_CODEX_CLIENT_VERSION")
	assert codex_client_version() == DEFAULT_CODEX_CLIENT_VERSION


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

	tools = [
		{
			"type": "function",
			"function": {
				"name": "bash",
				"description": "run",
				"parameters": {"type": "object"},
			},
		}
	]
	async with _mock_client(handler) as client:
		model = CodexModel(
			"codex/gpt-test",
			api_key="oauth-token",
			api_base="https://example.test/backend-api",
			headers={"chatgpt-account-id": "acc", "Authorization": "must-not-win"},
			client=client,
		)

		def run(stream):
			return _collect(
				model,
				[UserMessage(content="hi")],
				tools,
				system_prompt="be useful",
				stream=stream,
				max_output_tokens=12_345,
				tool_display_templates={"bash": "Running {{ command }}"},
			)

		events = await run(True)
		quiet = await run(False)

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
	# without streaming no live deltas go out, only the same final message
	assert [event.type for event in quiet] == ["assistant_message", "usage"]
	assert quiet[0].content == message.content


async def test_streamed_tool_calls_are_reported_once_with_their_stop_reason():
	bash_done = (
		'data: {"type":"response.output_item.done","item":'
		'{"type":"function_call","id":"item_1","call_id":"call_1",'
		'"name":"bash","arguments":"{\\"command\\":\\"pwd\\"}"}}'
	)
	parallel = [
		(
			'data: {"type":"response.output_item.added","item":'
			'{"type":"function_call","id":"item_1","call_id":"call_1","name":"bash"}}'
		),
		(
			'data: {"type":"response.output_item.added","item":'
			'{"type":"function_call","id":"item_2","call_id":"call_2","name":"read"}}'
		),
		bash_done,
		(
			'data: {"type":"response.output_item.done","item":'
			'{"type":"function_call","id":"item_2","call_id":"call_2",'
			'"name":"read","arguments":"{\\"path\\":\\"a.txt\\"}"}}'
		),
		'data: {"type":"response.completed","response":{}}',
	]
	incomplete = [
		bash_done,
		'data: {"type":"response.incomplete","response":{"id":"resp_1","usage":{}}}',
		"data: [DONE]",
	]
	cases = [
		# parallel calls are not duplicated by their done items
		(
			parallel,
			[("call_1", "bash", {"command": "pwd"}), ("call_2", "read", {"path": "a.txt"})],
			"tool_use",
		),
		# a truncated call is still reported, but keeps "length" over tool_use
		(incomplete, [("call_1", "bash", {"command": "pwd"})], "length"),
	]
	for lines, calls, stop_reason in cases:
		sse = "\n\n".join(lines)
		async with _mock_client(lambda _r: httpx.Response(200, text=sse)) as client:
			model = CodexModel("codex/gpt-test", api_key="token", client=client)
			events = await _collect(model, [UserMessage(content="hi")])

		message = events[-2]
		assert [(call.id, call.name, call.args) for call in message.tool_calls] == calls, stop_reason
		assert message.stop_reason == stop_reason


async def test_streams_reasoning_into_one_thinking_block():
	added = (
		'data: {"type":"response.output_item.added","item":{"type":"reasoning","id":"reason_1","summary":[]}}'
	)
	planning = "**Planning detailed single-file inspections**"
	starting = "**Starting sequential inspection phase**"
	cases = [
		(
			# summary deltas stream live; the done item seals the block
			[
				added,
				'data: {"type":"response.reasoning_summary_text.delta","item_id":"reason_1","delta":"weigh "}',
				'data: {"type":"response.reasoning_summary_text.delta","item_id":"reason_1","delta":"options"}',
				(
					'data: {"type":"response.output_item.done","item":'
					'{"type":"reasoning","id":"reason_1","encrypted_content":"opaque",'
					'"summary":[{"type":"summary_text","text":"weigh options"}]}}'
				),
			],
			["weigh ", "options"],
			"weigh options",
			"opaque",
		),
		(
			# boundaries between summary parts are kept
			[
				added,
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
			],
			[planning, f"\n\n{starting}"],
			f"{planning}\n\n{starting}",
			None,
		),
		(
			# streamed reasoning survives a done item that omits it
			[
				'data: {"type":"response.reasoning_text.delta","item_id":"reason_1","delta":"raw thought"}',
				(
					'data: {"type":"response.output_item.done","item":'
					'{"type":"reasoning","id":"reason_1","encrypted_content":"opaque"}}'
				),
			],
			["raw thought"],
			"raw thought",
			"opaque",
		),
	]
	for lines, deltas, text, encrypted in cases:
		sse = "\n\n".join([*lines, 'data: {"type":"response.completed","response":{}}'])
		async with _mock_client(lambda _r: httpx.Response(200, text=sse)) as client:
			model = CodexModel("codex/gpt-test", api_key="token", client=client)
			events = await _collect(model, [UserMessage(content="hi")])

		assert [event.type for event in events] == ["thinking_delta"] * len(deltas) + [
			"assistant_message",
			"usage",
		], text
		assert [event.thinking for event in events[: len(deltas)]] == deltas, text
		thinking = events[-2].content[0]
		assert isinstance(thinking, ThinkingContent), text
		assert thinking.thinking == text
		assert thinking.provider_state["item"].get("encrypted_content") == encrypted, text


# --- cancellation ----------------------------------------------------------


async def test_cancellation_releases_the_request_wherever_it_waits():
	class BlockingBody(httpx.AsyncByteStream):
		def __init__(self, head):
			self.head = head
			self.started = asyncio.Event()
			self.closed = asyncio.Event()

		async def __aiter__(self):
			if self.head:
				yield self.head
			self.started.set()
			await asyncio.Event().wait()

		async def aclose(self):
			self.closed.set()

	partial = b'data: {"type":"response.output_text.delta","delta":"partial"}\n\n'
	cases = [
		# (status, body head, events, text); no status: the headers never arrive
		(None, b"", ["assistant_message", "usage"], ""),
		(500, b"", ["assistant_message", "usage"], ""),
		(200, partial, ["text_delta", "assistant_message", "usage"], "partial"),
	]
	for status, head, types, text in cases:
		body = BlockingBody(head)

		async def handler(request):
			if status is None:
				body.started.set()
				try:
					await asyncio.Event().wait()
				finally:
					body.closed.set()
			return httpx.Response(status, stream=body)

		cancellation = asyncio.Event()
		async with _mock_client(handler) as client:
			model = CodexModel("codex/gpt-test", api_key="token", client=client)
			task = asyncio.create_task(
				_collect(model, [UserMessage(content="hi")], cancellation=cancellation)
			)
			await body.started.wait()
			cancellation.set()
			events = await asyncio.wait_for(task, timeout=1)

		assert body.closed.is_set(), status
		assert [event.type for event in events] == types, status
		assert events[-2].text == text, status
		assert events[-2].stop_reason == "aborted", status


# --- retries + refresh inside the adapter ----------------------------------


async def test_transient_failures_retry_in_stream(monkeypatch):
	# no backoff wait, while a provider's own retry hint still applies
	monkeypatch.setattr("flow_harness.model.retry._RETRY_BASE_DELAY_SECONDS", 0)
	overloaded = (
		'data: {"type":"error","error":{"type":"service_unavailable_error",'
		'"code":"server_is_overloaded","message":"server overloaded"}}'
	)

	def status(code):
		return lambda request: httpx.Response(
			code,
			headers={"retry-after": "0.001"},
			json={"error": {"message": "provider temporarily unavailable"}},
		)

	def stall(request):
		raise httpx.ReadTimeout("provider stalled", request=request)

	cases = [
		(status(429), "rate_limit", 0.001),
		(status(500), "overloaded", 0.001),
		(status(503), "overloaded", 0.001),
		(stall, "timeout", 0),
		# an error frame on a 200 stream, before the terminal commits
		(lambda request: httpx.Response(200, text=overloaded), "overloaded", 0),
	]
	for fail, kind, delay in cases:
		attempts = 0

		def handler(request):
			nonlocal attempts
			attempts += 1
			return fail(request) if attempts == 1 else httpx.Response(200, text=_success_sse())

		async with _mock_client(handler) as client:
			model = CodexModel("codex/gpt-test", api_key="token", client=client)
			events = await _collect(model, [UserMessage(content="hi")])

		assert attempts == 2, kind
		assert [event.type for event in events] == [
			"retry",
			"retry",
			"text_delta",
			"assistant_message",
			"usage",
		], kind
		retries = events[:2]
		assert [(retry.status, retry.attempt, retry.kind) for retry in retries] == [
			("scheduled", 2, kind),
			("started", 2, None),
		]
		assert retries[0].delay_seconds == delay, kind


async def test_permanent_failures_are_typed_and_not_retried():
	cases = [
		({"error": {"message": "invalid tool schema"}}, "invalid_request"),
		(
			{
				"error": {
					"code": "context_length_exceeded",
					"message": "Your input exceeds the context window of this model.",
				}
			},
			"context_overflow",
		),
	]
	for body, kind in cases:
		attempts = 0

		def handler(request):
			nonlocal attempts
			attempts += 1
			return httpx.Response(400, json=body)

		events = []
		async with _mock_client(handler) as client:
			model = CodexModel("codex/gpt-test", api_key="token", client=client)
			with pytest.raises(ProviderError) as raised:
				async for event in model.run(ModelRequest(messages=[UserMessage(content="hi")])):
					events.append(event)

		assert attempts == 1, kind
		assert events == [], kind
		assert raised.value.kind == kind


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


def test_replays_provider_identities_only_to_the_same_model():
	reasoning = {"type": "reasoning", "id": "reason_1", "encrypted_content": "opaque"}
	model = CodexModel("codex/gpt-test", api_key="token")

	def turn(content, source=model.model):
		return AssistantMessage(content=content, api=model.api, provider=model.provider, model=source)

	items = _responses_input(
		[
			turn(
				[
					ThinkingContent(thinking="", provider_state={"item": reasoning}),
					TextContent(text="working", provider_state={"id": "msg_1", "phase": "commentary"}),
					ToolCall(
						id="call_1",
						name="bash",
						arguments={},
						provider_state={"item_id": "item_1"},
					),
				]
			),
			ToolResult(tool_call_id="call_1", name="bash", content="ok"),
		],
		model,
	)

	assert items == [
		reasoning,
		{
			"type": "message",
			"role": "assistant",
			"content": [{"type": "output_text", "text": "working", "annotations": []}],
			"status": "completed",
			"id": "msg_1",
			"phase": "commentary",
		},
		{"type": "function_call", "call_id": "call_1", "name": "bash", "arguments": "{}", "id": "item_1"},
		{"type": "function_call_output", "call_id": "call_1", "output": "ok"},
	]

	# another model gets the reasoning summary as plain text
	other = turn(
		[ThinkingContent(thinking="safe summary", provider_state={"item": reasoning})], "codex/gpt-old"
	)
	assert _responses_input([other], model) == [
		{
			"type": "message",
			"role": "assistant",
			"content": [{"type": "output_text", "text": "safe summary", "annotations": []}],
			"status": "completed",
			"id": "msg_0",
		}
	]


def test_drops_failed_turns_and_the_results_answering_them():
	target = CodexModel("codex/gpt-test", api_key="token")

	def aborted(content):
		return AssistantMessage(
			content=content,
			api=target.api,
			provider=target.provider,
			model=target.model,
			stop_reason="aborted",
		)

	call = aborted([ToolCall(id="call_1", name="read", arguments={"path": "a.txt"})])
	repair = ToolResult(tool_call_id="call_1", name="read", content="interrupted", is_error=True)

	# a call and its answer must both be dropped
	assert _responses_input([aborted("partial"), call, repair], target) == []
