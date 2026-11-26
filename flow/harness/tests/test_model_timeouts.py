import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from flow_harness.events import AssistantMessage, Usage, UserMessage
from flow_harness.model import LiteLLMModel, ModelRequest


def _sse(**data):
	chunk = {
		"id": "chatcmpl-timeout",
		"object": "chat.completion.chunk",
		"created": 1,
		"model": "gpt-4o-mini",
		**data,
	}
	return f"data: {json.dumps(chunk)}\n\n".encode()


class SSEBody(httpx.AsyncByteStream):
	def __init__(self, ending, request):
		self.ending = ending
		self.request = request
		self.closed = False

	async def __aiter__(self):
		yield _sse(
			choices=[{"index": 0, "delta": {"content": "Completed answer."}, "finish_reason": "length"}]
		)
		yield _sse(
			choices=[],
			usage={
				"prompt_tokens": 123,
				"completion_tokens": 45,
				"total_tokens": 168,
				"cost": 0.0042,
				"prompt_tokens_details": {"cached_tokens": 23},
			},
		)
		if self.ending == "silence":
			await asyncio.Event().wait()
		else:
			raise httpx.ReadTimeout("post-finish read timed out", request=self.request)

	async def aclose(self):
		self.closed = True


@pytest.mark.parametrize("ending", ["silence", "read_timeout"])
async def test_completed_sse_response_survives_post_finish_timeout(monkeypatch, ending):
	bodies = []

	def handle(request):
		body = SSEBody(ending, request)
		bodies.append(body)
		return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=body)

	monkeypatch.setattr("flow_harness.model.retry._retry_delay_seconds", lambda error, retry_index: 0)
	async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http_client:
		async with AsyncOpenAI(
			api_key="test-key",
			base_url="https://provider.example.com/v1",
			http_client=http_client,
			max_retries=0,
		) as client:
			model = LiteLLMModel(
				"openai/gpt-4o-mini",
				params={"client": client, "timeout": 1},
				supports_images=False,
			)

			async def collect():
				return [
					event async for event in model.run(ModelRequest(messages=[UserMessage(content="hi")]))
				]

			events = await asyncio.wait_for(collect(), timeout=5)
			assert len(bodies) == 1
			assert bodies[0].closed
			assert not any(event.type == "retry" for event in events)
			messages = [event for event in events if isinstance(event, AssistantMessage)]
			assert len(messages) == 1
			assert (messages[0].text, messages[0].stop_reason) == ("Completed answer.", "length")
			assert events[-1] == Usage(
				input_tokens=123,
				output_tokens=45,
				cache_read_tokens=23,
				cost=0.0042,
			)
