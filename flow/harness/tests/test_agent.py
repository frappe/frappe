from flow_server.agent import Agent
from flow_server.events import AssistantMessage, ToolCall
from flow_server.model.mock import MockModel


async def test_run_streams_a_full_turn(tmp_path):
	mock = MockModel(replies=[AssistantMessage(text="hello world")])
	agent = Agent(model=mock, data_dir=str(tmp_path), cwd=str(tmp_path))
	types = [ev.type async for ev in agent.run("hi")]
	assert types[0] == "run_started"
	assert "assistant_message" in types
	assert types[-1] == "run_ended"


async def test_run_then_resume_across_pause(tmp_path):
	(tmp_path / "a.txt").write_text("SECRET")
	call = ToolCall(id="c1", name="read_file", args={"path": "a.txt"})
	mock = MockModel(replies=[AssistantMessage(tool_calls=[call]), AssistantMessage(text="done")])
	agent = Agent(
		model=mock, data_dir=str(tmp_path), cwd=str(tmp_path), confirm_tools=["read_file"]
	)

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
