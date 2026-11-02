"""The embedded facade: run/resume as live event iterators over one session."""

import asyncio

import pytest

from flow_harness.agent.agent import Agent
from flow_harness.events import (
	AssistantMessage,
	RunEnded,
	TextDelta,
	ThinkingContent,
	ThinkingDelta,
	ToolCall,
	Usage,
)
from flow_harness.model import Model, ModelRequest
from flow_harness.model.mock import MockModel


async def test_event_iterator_fails_cleanly_instead_of_hanging(tmp_path, monkeypatch):
	agent = Agent(
		model=MockModel(replies=[AssistantMessage(content="done")]),
		data_dir=str(tmp_path),
		cwd=str(tmp_path),
	)
	original_append = agent.session.log.append

	def fail_terminal(event):
		if isinstance(event, RunEnded):
			raise OSError("log unavailable")
		return original_append(event)

	monkeypatch.setattr(agent.session.log, "append", fail_terminal)

	async def consume():
		return [event async for event in agent.run("hi")]

	with pytest.raises(OSError, match="log unavailable"):
		await asyncio.wait_for(consume(), timeout=0.5)
	assert agent.session.is_running is False

	# a subscriber that falls behind is cut off with an error
	monkeypatch.setattr("flow_harness.session.session._SUBSCRIBER_QUEUE_SIZE", 2)

	class BurstyModel(Model):
		name = "bursty"

		def __init__(self):
			self.finished = asyncio.Event()

		async def run(self, request: ModelRequest):
			for text in ("a", "b", "c"):
				yield TextDelta(text=text)
			yield AssistantMessage(content="abc")
			yield Usage()
			self.finished.set()

	model = BurstyModel()
	agent = Agent(model=model, data_dir=str(tmp_path), cwd=str(tmp_path))
	events = agent.run("hi")
	assert (await anext(events)).type == "run_started"
	await model.finished.wait()

	with pytest.raises(RuntimeError, match="subscriber fell behind"):
		await anext(events)
	assert agent.session.is_running is False


async def test_run_then_resume_across_pause(tmp_path):
	(tmp_path / "a.txt").write_text("SECRET")
	call = ToolCall(id="c1", name="read", arguments={"path": "a.txt"})
	mock = MockModel(replies=[AssistantMessage(content=[call]), AssistantMessage(content="done")])
	agent = Agent(model=mock, data_dir=str(tmp_path), cwd=str(tmp_path), confirm_tools=["read"])

	events = [ev async for ev in agent.run("read it")]
	types = [ev.type for ev in events]
	assert types[0] == "run_started"
	assert "assistant_message" in types
	assert types[-1] == "run_ended"
	pending = next(ev.calls for ev in events if ev.type == "approval_required")
	assert pending[0].id == "c1"

	results = [ev async for ev in agent.resume({"c1": "Approve"})]
	tool_results = [ev for ev in results if ev.type == "tool_result"]
	assert tool_results[0].content == "SECRET"
	assert results[-1].type == "run_ended"
	assert results[-1].reason == "done"


async def test_abort_keeps_the_streamed_content_and_the_next_run_gets_a_fresh_signal(tmp_path):
	class AbortThenFinishModel(Model):
		name = "abort-then-finish"

		def __init__(self):
			self.calls = 0
			self.started = asyncio.Event()
			self.cancelled = asyncio.Event()

		async def run(self, request: ModelRequest):
			self.calls += 1
			if self.calls == 1:
				yield ThinkingDelta(thinking="checking")
				yield TextDelta(text="Partial answer")
				self.started.set()
				try:
					await asyncio.Event().wait()
				finally:
					self.cancelled.set()
				return
			assert request.cancellation is not None
			assert not request.cancellation.is_set()
			yield AssistantMessage(content="recovered")
			yield Usage()

	model = AbortThenFinishModel()
	agent = Agent(model=model, data_dir=str(tmp_path), cwd=str(tmp_path))

	first = asyncio.create_task(_collect(agent.run("wait")))
	await model.started.wait()
	assert agent.abort() is True
	events = await asyncio.wait_for(first, timeout=1)

	assert model.cancelled.is_set()
	[assistant] = [event for event in events if event.type == "assistant_message"]
	assert assistant.stop_reason == "aborted"
	assert isinstance(assistant.content[0], ThinkingContent)
	assert assistant.thinking_text == "checking"
	assert assistant.text == "Partial answer"
	assert agent.session.transcript.messages[-1] == assistant
	assert events[-1].type == "run_ended"
	assert events[-1].reason == "aborted"
	assert agent.session.is_running is False
	assert agent.abort() is False

	second = await _collect(agent.run("try again"))
	assert [event.text for event in second if event.type == "assistant_message"] == ["recovered"]
	assert second[-1].reason == "done"


async def test_set_model_records_a_name_but_refuses_an_injected_model(tmp_path):
	agent = Agent(model="mock", data_dir=str(tmp_path), cwd=str(tmp_path))
	await agent.set_model("mock/v2")
	assert agent.session.model == "mock/v2"

	mock = MockModel(replies=[AssistantMessage(content="hello")])
	agent = Agent(model=mock, data_dir=str(tmp_path), cwd=str(tmp_path))
	with pytest.raises(RuntimeError, match="injected Model instance"):
		await agent.set_model("mock/v2")
	assert agent.session.log.latest_seq == 0  # nothing durable was recorded


async def _collect(events):
	return [event async for event in events]


async def test_compact_streams_the_operation(tmp_path):
	mock = MockModel(
		replies=[
			AssistantMessage(content="an answer"),
			AssistantMessage(content="## Goal\nagent summary"),
		]
	)
	agent = Agent(model=mock, data_dir=str(tmp_path), cwd=str(tmp_path))
	async for _ in agent.run("hi"):
		pass

	types = [ev.type async for ev in agent.compact()]

	assert types[0] == "run_started"
	assert "compaction_started" in types and "compaction" in types
	assert types[-1] == "run_ended"
	assert agent.session.transcript.messages[0].content.startswith("Previous conversation summary:")
