import json

import httpx

from flow_server.events import (
	AssistantMessage,
	TextContent,
	ThinkingContent,
	ToolCall,
	ToolResult,
	UserMessage,
)
from flow_server.model.providers.codex import CodexModel, _responses_input


async def _collect(model, messages, tools=None, *, system_prompt="", stream=True):
	return [
		event
		async for event in model.run(
			messages,
			tools,
			system_prompt=system_prompt,
			stream=stream,
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
