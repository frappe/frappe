"""Phase 6 TUI shell: rendering, delta→durable swap, steering, queueing, status bar.

Pilot tests drive `FlowApp` with a fake controller (no HTTP); one integration test
runs the real stack — uvicorn + MockModel + Controller — end to end.
"""

import asyncio
import socket
from collections.abc import Callable
from contextlib import asynccontextmanager

import uvicorn

from flow.events import (
	AssistantMessage,
	RunEnded,
	RunStarted,
	TextContent,
	TextDelta,
	ToolResult,
	Usage,
	UserMessage,
)
from flow.model.credentials import CredentialStore
from flow.server import create_app
from flow.session.config import SessionConfig
from flow.session.store import SessionStore
from flow_tui.app import FlowApp
from flow_tui.client.api import FlowClient
from flow_tui.client.state import Change, ConversationState, StatusChanged
from flow_tui.controller import Controller
from flow_tui.widgets.composer import Composer
from flow_tui.widgets.conversation import ConversationView
from flow_tui.widgets.messages import EntryView, PartialAssistantView
from flow_tui.widgets.status_bar import StatusBar


class FakeController:
	"""Same surface the app consumes, but events are fed by the test."""

	def __init__(self):
		self.state = ConversationState()
		self.queued: list[str] = []
		self.steered_seqs: set[int] = set()
		self.session_id: str | None = "fake-session-id"
		self.on_changes: Callable[[list[Change]], None] = lambda changes: None
		self.calls = []

	async def connect(self):
		self.on_changes([StatusChanged()])

	async def stream_events(self):
		await asyncio.Event().wait()

	async def submit(self, text):
		self.calls.append(("submit", text))
		return "steered" if self.state.running else "started"

	def queue(self, text):
		self.queued.append(text)
		self.on_changes([StatusChanged()])

	async def abort(self):
		self.calls.append(("abort",))

	async def stop(self):
		pass

	def feed(self, event):
		changes = self.state.apply(event)
		if changes:
			self.on_changes(changes)


def _widget_text(widget) -> str:
	return str(widget.render())


async def test_renders_entries_and_swaps_partial_for_durable():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		fake.feed(RunStarted(run_id="r1", seq=1))
		fake.feed(UserMessage(content="hello", seq=2))
		fake.feed(TextDelta(text="Mock "))
		fake.feed(TextDelta(text="reply"))
		await pilot.pause()

		conversation = pilot.app.query_one(ConversationView)
		assert len(conversation.query(EntryView)) == 1  # the user message
		partial = conversation.query_one(PartialAssistantView)
		assert "Mock reply" in _widget_text(partial)

		fake.feed(AssistantMessage(content=[TextContent(text="Mock reply, final")], seq=3))
		fake.feed(RunEnded(seq=4))
		await pilot.pause()

		assert not conversation.query(PartialAssistantView)  # swapped, not appended
		entries = conversation.query(EntryView)
		assert len(entries) == 2
		assert "Mock reply, final" in _widget_text(entries.last())


async def test_tool_result_renders_preview():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		fake.feed(ToolResult(tool_call_id="t1", name="bash", content="line1\nline2", seq=1))
		await pilot.pause()
		text = _widget_text(pilot.app.query_one(ConversationView).query(EntryView).last())
		assert "bash" in text and "line1" in text


async def test_enter_submits_and_enter_while_running_steers():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await pilot.press("h", "i", "enter")
		await pilot.pause()
		assert fake.calls == [("submit", "hi")]
		assert pilot.app.query_one(Composer).text == ""

		fake.feed(RunStarted(run_id="r1", seq=1))
		fake.feed(UserMessage(content="hi", seq=2))
		await pilot.press("g", "o", "enter")
		await pilot.pause()
		assert fake.calls[-1] == ("submit", "go")  # server-side steering; app just sends


async def test_alt_enter_queues_while_running():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		fake.feed(RunStarted(run_id="r1", seq=1))
		await pilot.press("q", "1", "alt+enter")
		await pilot.pause()
		assert fake.queued == ["q1"]
		assert fake.calls == []
		assert "1 queued" in _widget_text(pilot.app.query_one(StatusBar))


async def test_escape_aborts_running_run():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		fake.feed(RunStarted(run_id="r1", seq=1))
		await pilot.press("escape")
		await pilot.pause()
		assert ("abort",) in fake.calls


async def test_status_bar_reflects_state():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		fake.state.model = "mock"
		fake.feed(RunStarted(run_id="r1", seq=1))
		await pilot.pause()
		text = _widget_text(pilot.app.query_one(StatusBar))
		assert "mock" in text and "running" in text and "fake-ses" in text

		fake.feed(Usage(input_tokens=10, output_tokens=5, cost=0.5, seq=2))
		fake.feed(RunEnded(seq=3))
		await pilot.pause()
		text = _widget_text(pilot.app.query_one(StatusBar))
		assert "idle" in text and "Σ 15 tok" in text and "$0.5000" in text


# --- integration: real server + controller ---------------------------------


@asynccontextmanager
async def _live_server(tmp_path):
	store = SessionStore(
		str(tmp_path / "data"),
		credential_store=CredentialStore(str(tmp_path / "credentials.json")),
	)
	sock = socket.socket()
	sock.bind(("127.0.0.1", 0))
	port = sock.getsockname()[1]
	server = uvicorn.Server(uvicorn.Config(create_app(store), log_level="error", timeout_graceful_shutdown=1))
	task = asyncio.create_task(server.serve(sockets=[sock]))
	try:
		while not server.started:
			await asyncio.sleep(0.01)
		yield f"http://127.0.0.1:{port}"
	finally:
		server.should_exit = True
		await asyncio.wait_for(task, timeout=5)


async def test_integration_conversation_over_live_server(tmp_path):
	async with _live_server(tmp_path) as url:
		client = FlowClient(url)
		config = SessionConfig(model="mock", cwd=str(tmp_path), auto_approve=True)
		controller = Controller(client, config=config)
		async with FlowApp(controller).run_test() as pilot:
			async with asyncio.timeout(5):
				while controller.session_id is None:
					await pilot.pause(0.05)

			await pilot.press("h", "i", "enter")
			conversation = pilot.app.query_one(ConversationView)

			def replied():
				entries = conversation.query(EntryView)
				return any("Mock reply to: hi" in _widget_text(e) for e in entries)

			async with asyncio.timeout(10):
				while not replied():
					await pilot.pause(0.05)

			assert not controller.state.running
			assert "idle" in _widget_text(pilot.app.query_one(StatusBar))
