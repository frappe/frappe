import json

import httpx

from flow_server.model.providers.codex import CodexModel, _responses_input


async def _collect(model, messages, tools=None, *, stream=True):
	return [event async for event in model.run(messages, tools, stream=stream)]


async def test_codex_model_streams_text_tools_and_usage():
	captured = {}
	sse = "\n\n".join(
		[
			'data: {"type":"response.output_text.delta","delta":"hello "}',
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
				'data: {"type":"response.completed","response":{"usage":'
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
			[{"role": "system", "content": "be useful"}, {"role": "user", "content": "hi"}],
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
	assert events[-2].provider_data["codex_reasoning"][0]["id"] == "reason_1"
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
		events = await _collect(model, [{"role": "user", "content": "hi"}], stream=False)

	assert [event.type for event in events] == ["assistant_message", "usage"]
	assert events[0].text == "done"


def test_codex_replays_opaque_reasoning_before_tool_turn():
	reasoning = {"type": "reasoning", "id": "reason_1", "encrypted_content": "opaque"}
	_, items = _responses_input(
		[
			{
				"role": "assistant",
				"content": None,
				"provider_data": {"codex_reasoning": [reasoning]},
				"tool_calls": [
					{
						"id": "call_1|item_1",
						"function": {"name": "bash", "arguments": "{}"},
					}
				],
			},
			{"role": "tool", "tool_call_id": "call_1|item_1", "content": "ok"},
		]
	)

	assert items[0] == reasoning
	assert items[1]["type"] == "function_call"
	assert items[2] == {"type": "function_call_output", "call_id": "call_1", "output": "ok"}
