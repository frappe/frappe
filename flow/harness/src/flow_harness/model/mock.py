"""A keyless, deterministic model for tests and offline dogfooding.

By default it echoes the latest user message. Pass `replies` to script exact assistant
turns (text and/or tool calls), one consumed per `run` call — enough to drive
multi-turn agent-loop tests (tool call -> resume -> final answer) with no provider.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from flow_harness.events import (
	AnyEvent,
	AssistantMessage,
	TextContent,
	TextDelta,
	ToolCallStarted,
	TranscriptMessage,
	Usage,
	UserMessage,
)
from flow_harness.model.base import Model, ModelRequest
from flow_harness.model.tool_display import tool_call_display_ready_event, with_tool_call_displays


class MockModel(Model):
	name = "mock"
	api = "mock"
	provider = "mock"
	model = "mock"

	def __init__(
		self,
		replies: list[AssistantMessage] | None = None,
		*,
		context_window: int | None = None,
	):
		self._replies = replies
		self._turn = 0
		self._context_window = context_window

	@property
	def context_window(self) -> int | None:
		return self._context_window

	async def run(self, request: ModelRequest) -> AsyncIterator[AnyEvent]:
		if request.cancellation is not None and request.cancellation.is_set():
			yield self.aborted_message()
			yield Usage()
			return
		reply = self._next_reply(request.messages)
		if request.stream:
			for piece in _chunk(reply.text):
				yield TextDelta(text=piece)
			for call in reply.tool_calls:
				yield ToolCallStarted(id=call.id, name=call.name)
				ready = tool_call_display_ready_event(
					call.id,
					call.name,
					call.arguments,
					display_template=request.tool_display_templates.get(call.name),
				)
				if ready is not None:
					yield ready
		message = reply.model_copy(
			update={
				"api": self.api,
				"provider": self.provider,
				"model": self.name,
				# mirrors the real adapters: only a plain stop upgrades, so a scripted
				# "length" survives and the loop can be tested against a truncated turn
				"stop_reason": (
					"tool_use" if reply.tool_calls and reply.stop_reason == "stop" else reply.stop_reason
				),
			}
		)
		yield with_tool_call_displays(message, request.tool_display_templates)
		yield Usage(
			input_tokens=_estimate(_last_user(request.messages)),
			output_tokens=_estimate(reply.text),
		)

	def _next_reply(self, messages: list[TranscriptMessage]) -> AssistantMessage:
		if self._replies is None:
			return AssistantMessage(content=[TextContent(text=f"Mock reply to: {_last_user(messages)}")])
		if self._turn >= len(self._replies):
			return AssistantMessage()
		reply = self._replies[self._turn]
		self._turn += 1
		return reply


def _last_user(messages: list[TranscriptMessage]) -> str:
	for message in reversed(messages):
		if isinstance(message, UserMessage):
			return message.text
	return ""


def _chunk(text: str) -> list[str]:
	"""Split into space-preserving word pieces so a streaming consumer sees several deltas."""
	if not text:
		return []
	words = text.split(" ")
	return [w + (" " if i < len(words) - 1 else "") for i, w in enumerate(words)]


def _estimate(text: str) -> int:
	return max(1, len(text) // 4) if text else 0
