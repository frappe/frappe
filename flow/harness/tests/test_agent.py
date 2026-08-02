"""The embedded facade: run/resume as live event iterators over one session."""

import asyncio

import pytest

from flow.agent.agent import Agent
from flow.events import AssistantMessage, RunEnded, ToolCall, Usage
from flow.model import Model, ModelRequest
from flow.model.mock import MockModel


async def test_run_streams_a_full_turn(tmp_path):
	mock = MockModel(replies=[AssistantMessage(content="hello world")])
	agent = Agent(model=mock, data_dir=str(tmp_path), cwd=str(tmp_path))
	types = [ev.type async for ev in agent.run("hi")]
	assert types[0] == "run_started"
	assert "assistant_message" in types
	assert types[-1] == "run_ended"


async def test_run_then_resume_across_pause(tmp_path):
	(tmp_path / "a.txt").write_text("SECRET")
	call = ToolCall(id="c1", name="read_file", arguments={"path": "a.txt"})
	mock = MockModel(replies=[AssistantMessage(content=[call]), AssistantMessage(content="done")])
	agent = Agent(model=mock, data_dir=str(tmp_path), cwd=str(tmp_path), confirm_tools=["read_file"])

	pending = None
	async for ev in agent.run("read it"):
		if ev.type == "approval_required":
			pending = ev.calls
	assert pending and pending[0].id == "c1"

	results = [ev async for ev in agent.resume({"c1": "Approve"})]
	tool_results = [ev for ev in results if ev.type == "tool_result"]
	assert tool_results[0].content == "SECRET"
	assert results[-1].type == "run_ended"
	assert results[-1].reason == "done"


async def test_event_iterator_does_not_hang_if_terminal_commit_fails(tmp_path, monkeypatch):
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


async def test_abort_stops_in_process_run_and_next_run_gets_fresh_signal(tmp_path):
	class AbortThenFinishModel(Model):
		name = "abort-then-finish"

		def __init__(self):
			self.calls = 0
			self.started = asyncio.Event()
			self.cancelled = asyncio.Event()

		async def run(self, request: ModelRequest):
			self.calls += 1
			if self.calls == 1:
				self.started.set()
				try:
					await asyncio.Event().wait()
				finally:
					self.cancelled.set()
				if False:
					yield
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
	assert [event.stop_reason for event in events if event.type == "assistant_message"] == ["aborted"]
	assert events[-1].type == "run_ended"
	assert events[-1].reason == "aborted"
	assert agent.session.is_running is False
	assert agent.abort() is False

	second = await _collect(agent.run("try again"))
	assert [event.text for event in second if event.type == "assistant_message"] == ["recovered"]
	assert second[-1].reason == "done"


async def test_set_model_records_for_a_name_constructed_agent(tmp_path):
	agent = Agent(model="mock", data_dir=str(tmp_path), cwd=str(tmp_path))
	await agent.set_model("mock/v2")
	assert agent.session.model == "mock/v2"


async def test_set_model_conflicts_with_an_injected_model_instance(tmp_path):
	mock = MockModel(replies=[AssistantMessage(content="hello")])
	agent = Agent(model=mock, data_dir=str(tmp_path), cwd=str(tmp_path))
	with pytest.raises(RuntimeError, match="injected Model instance"):
		await agent.set_model("mock/v2")
	assert agent.session.log.latest_seq == 0  # nothing durable was recorded


async def _collect(events):
	return [event async for event in events]
