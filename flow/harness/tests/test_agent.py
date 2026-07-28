import asyncio

import pytest

from flow_server.agent import Agent
from flow_server.events import AssistantMessage, RunEnded, ToolCall
from flow_server.model.mock import MockModel


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


async def test_event_iterator_does_not_hang_if_terminal_publish_fails(tmp_path, monkeypatch):
	agent = Agent(
		model=MockModel(replies=[AssistantMessage(content="done")]),
		data_dir=str(tmp_path),
		cwd=str(tmp_path),
	)
	original_publish = agent.session.publish

	def fail_terminal(event):
		if isinstance(event, RunEnded):
			raise OSError("log unavailable")
		original_publish(event)

	monkeypatch.setattr(agent.session, "publish", fail_terminal)

	async def consume():
		return [event async for event in agent.run("hi")]

	with pytest.raises(OSError, match="log unavailable"):
		await asyncio.wait_for(consume(), timeout=0.5)
	assert agent.session.is_running is False
