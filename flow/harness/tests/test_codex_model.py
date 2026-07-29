import asyncio
import json

import httpx
import pytest

import flow_server.agent.loop as agent_loop
from flow_server.agent import run
from flow_server.events import (
	AssistantMessage,
	TextContent,
	ThinkingContent,
	ToolCall,
	ToolResult,
	UserMessage,
)
from flow_server.model import ModelRequest
from flow_server.model.providers.codex import CodexModel, _responses_input
from flow_server.session.store import SessionConfig, SessionStore


async def _collect(
	model,
	messages,
	tools=None,
	*,
	system_prompt="",
	stream=True,
	cancellation=None,
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
			)
		)
	]


async def test_codex_model_streams_text_tools_and_usage():
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
				'{"input_tokens":12,"output_tokens":4}}}'
			),
			"data: [DONE]",
		]
	)

	def handler(request):
		captured["url"] = str(request.url)
		captured["headers"] = dict(request.headers)
		captured["payload"] = json.loads(request.content)
		return httpx.Response(200, text=sse)

	async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
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
		)

	assert captured["url"] == "https://example.test/backend-api/codex/responses"
	assert captured["headers"]["authorization"] == "Bearer oauth-token"
	assert captured["payload"]["model"] == "gpt-test"
	assert captured["payload"]["instructions"] == "be useful"
	assert captured["payload"]["tools"][0]["name"] == "bash"
	assert [event.type for event in events] == [
		"text_delta",
		"tool_call_started",
		"assistant_message",
		"usage",
	]
	assert events[-2].text == "hello "
	assert events[-2].tool_calls[0].id == "call_1|item_1"
	assert events[-2].tool_calls[0].args == {"command": "pwd"}
	assert [block.type for block in events[-2].content] == ["text", "thinking", "tool_call"]
	assert json.loads(events[-2].content[0].text_signature) == {
		"v": 1,
		"id": "msg_1",
		"phase": "commentary",
	}
	thinking = events[-2].content[1]
	assert isinstance(thinking, ThinkingContent)
	assert json.loads(thinking.thinking_signature)["id"] == "reason_1"
	assert events[-2].api == "openai-codex-responses"
	assert events[-2].provider == "codex"
	assert events[-2].model == "codex/gpt-test"
	assert events[-2].response_model == "gpt-concrete"
	assert events[-2].response_id == "resp_1"
	assert events[-2].stop_reason == "tool_use"
	assert events[-1].input_tokens == 12
	assert events[-1].output_tokens == 4


async def test_codex_incomplete_response_keeps_length_over_tool_use():
	sse = "\n\n".join(
		[
			(
				'data: {"type":"response.output_item.done","item":'
				'{"type":"function_call","id":"item_1","call_id":"call_1",'
				'"name":"bash","arguments":"{\\"command\\":\\"pwd\\"}"}}'
			),
			('data: {"type":"response.incomplete","response":{"id":"resp_1","usage":{}}}'),
			"data: [DONE]",
		]
	)

	async with httpx.AsyncClient(
		transport=httpx.MockTransport(lambda _r: httpx.Response(200, text=sse))
	) as client:
		model = CodexModel("codex/gpt-test", api_key="t", api_base="https://e.test", client=client)
		events = await _collect(model, [UserMessage(content="hi")])

	assert events[-2].tool_calls  # the truncated call is still reported
	assert events[-2].stop_reason == "length"


async def test_codex_non_streaming_suppresses_live_deltas():
	sse = "\n\n".join(
		[
			'data: {"type":"response.output_text.delta","delta":"done"}',
			'data: {"type":"response.completed","response":{}}',
		]
	)

	def handler(request):
		return httpx.Response(200, text=sse)

	async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		events = await _collect(model, [UserMessage(content="hi")], stream=False)

	assert [event.type for event in events] == ["assistant_message", "usage"]
	assert events[0].text == "done"


async def test_codex_streams_reasoning_summary_deltas():
	sse = "\n\n".join(
		[
			(
				'data: {"type":"response.output_item.added","item":'
				'{"type":"reasoning","id":"reason_1","summary":[]}}'
			),
			('data: {"type":"response.reasoning_summary_text.delta","item_id":"reason_1","delta":"weigh "}'),
			('data: {"type":"response.reasoning_summary_text.delta","item_id":"reason_1","delta":"options"}'),
			(
				'data: {"type":"response.output_item.done","item":'
				'{"type":"reasoning","id":"reason_1","encrypted_content":"opaque",'
				'"summary":[{"type":"summary_text","text":"weigh options"}]}}'
			),
			'data: {"type":"response.completed","response":{}}',
		]
	)

	def handler(request):
		return httpx.Response(200, text=sse)

	async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
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
	assert json.loads(thinking.thinking_signature)["encrypted_content"] == "opaque"


async def test_codex_keeps_streamed_reasoning_when_the_done_item_omits_it():
	sse = "\n\n".join(
		[
			('data: {"type":"response.reasoning_text.delta","item_id":"reason_1","delta":"raw thought"}'),
			(
				'data: {"type":"response.output_item.done","item":'
				'{"type":"reasoning","id":"reason_1","encrypted_content":"opaque"}}'
			),
			'data: {"type":"response.completed","response":{}}',
		]
	)

	def handler(request):
		return httpx.Response(200, text=sse)

	async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		events = await _collect(model, [UserMessage(content="hi")])

	thinking = events[-2].content[0]
	assert isinstance(thinking, ThinkingContent)
	assert thinking.thinking == "raw thought"
	assert json.loads(thinking.thinking_signature)["encrypted_content"] == "opaque"


async def test_codex_cancellation_closes_active_http_stream():
	class BlockingSSE(httpx.AsyncByteStream):
		def __init__(self):
			self.started = asyncio.Event()
			self.closed = asyncio.Event()

		async def __aiter__(self):
			yield (b'data: {"type":"response.output_text.delta","delta":"partial"}\n\n')
			self.started.set()
			await asyncio.Event().wait()

		async def aclose(self):
			self.closed.set()

	body = BlockingSSE()

	def handler(request):
		return httpx.Response(200, stream=body)

	cancellation = asyncio.Event()
	async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		task = asyncio.create_task(
			_collect(
				model,
				[UserMessage(content="hi")],
				cancellation=cancellation,
			)
		)
		await body.started.wait()
		cancellation.set()
		events = await asyncio.wait_for(task, timeout=1)

	assert body.closed.is_set()
	assert [event.type for event in events] == ["text_delta", "assistant_message", "usage"]
	assert events[-2].text == "partial"
	assert events[-2].stop_reason == "aborted"


async def test_codex_cancellation_interrupts_response_header_wait():
	request_started = asyncio.Event()
	request_cancelled = asyncio.Event()

	async def handler(request):
		request_started.set()
		try:
			await asyncio.Event().wait()
		finally:
			request_cancelled.set()

	cancellation = asyncio.Event()
	async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		task = asyncio.create_task(_collect(model, [UserMessage(content="hi")], cancellation=cancellation))
		await request_started.wait()
		cancellation.set()
		events = await asyncio.wait_for(task, timeout=1)

	assert request_cancelled.is_set()
	assert [event.type for event in events] == ["assistant_message", "usage"]
	assert events[0].stop_reason == "aborted"


async def test_codex_cancellation_interrupts_error_body_read_and_closes_stream():
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

	def handler(request):
		return httpx.Response(500, stream=body)

	cancellation = asyncio.Event()
	async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		task = asyncio.create_task(_collect(model, [UserMessage(content="hi")], cancellation=cancellation))
		await body.started.wait()
		cancellation.set()
		events = await asyncio.wait_for(task, timeout=1)

	assert body.closed.is_set()
	assert [event.type for event in events] == ["assistant_message", "usage"]
	assert events[0].stop_reason == "aborted"


def _success_sse(text="ok"):
	return "\n\n".join(
		[
			f'data: {{"type":"response.output_text.delta","delta":"{text}"}}',
			'data: {"type":"response.completed","response":{}}',
		]
	)


def _retry_session(tmp_path):
	events: list[dict] = []
	store = SessionStore(
		str(tmp_path / "data"),
		event_sink=lambda _sid, event: events.append(event),
	)
	session = store.create(
		SessionConfig(
			model="codex/gpt-test",
			cwd=str(tmp_path),
		)
	)
	return session, events


@pytest.mark.parametrize("status", [429, 500, 503])
async def test_codex_http_transient_failure_retries_through_agent_loop(tmp_path, status):
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

	async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		session, events = _retry_session(tmp_path)
		await run(session, "hello", model=model)

	assert attempts == 2
	assert [event["attempt"] for event in events if event["type"] == "retry_scheduled"] == [2]
	assert [event["delay_seconds"] for event in events if event["type"] == "retry_scheduled"] == [0.0]
	assert [event["reason"] for event in events if event["type"] == "run_ended"] == ["done"]


async def test_codex_timeout_retries_through_agent_loop(tmp_path, monkeypatch):
	attempts = 0

	def handler(request):
		nonlocal attempts
		attempts += 1
		if attempts == 1:
			raise httpx.ReadTimeout("provider stalled", request=request)
		return httpx.Response(200, text=_success_sse())

	monkeypatch.setattr(agent_loop, "_retry_delay_seconds", lambda error, retry_index: 0)
	async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		session, events = _retry_session(tmp_path)
		await run(session, "hello", model=model)

	assert attempts == 2
	assert [event["kind"] for event in events if event["type"] == "retry_scheduled"] == ["timeout"]
	assert [event["reason"] for event in events if event["type"] == "run_ended"] == ["done"]


async def test_codex_invalid_request_does_not_retry(tmp_path):
	attempts = 0

	def handler(request):
		nonlocal attempts
		attempts += 1
		return httpx.Response(400, json={"error": {"message": "invalid tool schema"}})

	async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		session, events = _retry_session(tmp_path)
		await run(session, "hello", model=model)

	assert attempts == 1
	assert [event for event in events if event["type"] == "retry_scheduled"] == []
	assert [event["kind"] for event in events if event["type"] == "run_error"] == ["invalid_request"]
	assert [event["reason"] for event in events if event["type"] == "run_ended"] == ["error"]


async def test_codex_context_overflow_is_typed_and_not_retried(tmp_path):
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

	async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		session, events = _retry_session(tmp_path)
		await run(session, "hello", model=model)

	assert attempts == 1
	assert [event for event in events if event["type"] == "retry_scheduled"] == []
	assert [event["kind"] for event in events if event["type"] == "run_error"] == ["context_overflow"]


async def test_codex_in_stream_overload_retries_before_terminal_commit(tmp_path):
	attempts = 0
	overloaded = (
		'data: {"type":"error","error":{"type":"service_unavailable_error",'
		'"code":"server_is_overloaded","message":"server overloaded"}}'
	)

	def handler(request):
		nonlocal attempts
		attempts += 1
		return httpx.Response(200, text=overloaded if attempts == 1 else _success_sse())

	async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
		model = CodexModel("codex/gpt-test", api_key="token", client=client)
		session, events = _retry_session(tmp_path)
		await run(session, "hello", model=model)

	assert attempts == 2
	assert [event["kind"] for event in events if event["type"] == "retry_scheduled"] == ["overloaded"]
	assert len([row for row in session.log.read_since(0) if row["type"] == "assistant_message"]) == 1


def test_codex_replays_opaque_reasoning_before_tool_turn():
	reasoning = {"type": "reasoning", "id": "reason_1", "encrypted_content": "opaque"}
	model = CodexModel("codex/gpt-test", api_key="token")
	items = _responses_input(
		[
			AssistantMessage(
				content=[
					ThinkingContent(
						thinking="",
						thinking_signature=json.dumps(reasoning),
					),
					ToolCall(id="call_1|item_1", name="bash", arguments={}),
				],
				api=model.api,
				provider=model.provider,
				model=model.model,
			),
			ToolResult(tool_call_id="call_1|item_1", name="bash", content="ok"),
		],
		model,
	)

	assert items[0] == reasoning
	assert items[1]["type"] == "function_call"
	assert items[2] == {"type": "function_call_output", "call_id": "call_1", "output": "ok"}


def test_codex_replays_text_item_identity_and_phase_to_the_same_model():
	model = CodexModel("codex/gpt-test", api_key="token")
	signature = json.dumps({"v": 1, "id": "msg_1", "phase": "commentary"})
	items = _responses_input(
		[
			AssistantMessage(
				content=[TextContent(text="working", text_signature=signature)],
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


def test_codex_does_not_replay_reasoning_to_a_different_model():
	reasoning = {"type": "reasoning", "id": "reason_1", "encrypted_content": "opaque"}
	target = CodexModel("codex/gpt-new", api_key="token")
	items = _responses_input(
		[
			AssistantMessage(
				content=[
					ThinkingContent(
						thinking="safe summary",
						thinking_signature=json.dumps(reasoning),
					)
				],
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


def test_codex_does_not_replay_aborted_assistant_response():
	target = CodexModel("codex/gpt-test", api_key="token")
	aborted = AssistantMessage(
		content="partial",
		api=target.api,
		provider=target.provider,
		model=target.model,
		stop_reason="aborted",
	)

	assert _responses_input([aborted], target) == []
