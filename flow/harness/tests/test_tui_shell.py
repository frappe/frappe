"""Phases 6-7 TUI shell: rendering, delta→durable swap, steering, queueing, status
bar, foldable thinking, and detail-driven tool-result rendering.

Pilot tests drive `FlowApp` with a fake controller (no HTTP); one integration test
runs the real stack — uvicorn + MockModel + Controller — end to end, through a
`/resume` switch.
"""

import asyncio
import socket
from collections.abc import Callable
from contextlib import asynccontextmanager

import uvicorn
from rich.console import Group
from rich.syntax import Syntax
from textual.widgets import Static

from flow_harness.events import (
	AssistantMessage,
	RunEnded,
	RunStarted,
	TextContent,
	TextDelta,
	ThinkingContent,
	ThinkingDelta,
	ToolCall,
	ToolCallStarted,
	ToolResult,
	Usage,
	UserMessage,
)
from flow_harness.model.credentials import CredentialStore
from flow_harness.server import create_app
from flow_harness.session.config import SessionConfig
from flow_harness.session.store import SessionStore
from flow_tui.app import SPINNER_FRAMES, FlowApp, Spinner
from flow_tui.client.api import FlowClient
from flow_tui.client.state import (
	Change,
	ConversationState,
	StatusChanged,
)
from flow_tui.controller import Controller
from flow_tui.widgets.composer import Composer
from flow_tui.widgets.conversation import ConversationView
from flow_tui.widgets.messages import (
	THINKING_MARKER,
	EntryView,
	PartialAssistantView,
	ThinkingBlock,
	ToolCallView,
)
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
	"""All visible text of a widget: its own render plus every child static."""
	if isinstance(widget, Static):
		return _render_str(widget)
	return "\n".join(_render_str(static) for static in widget.query(Static))


def _render_str(static: Static) -> str:
	rendered = static.render()
	rendered = getattr(rendered, "_renderable", rendered)  # unwrap textual's RichVisual
	return _renderable_str(rendered)


def _renderable_str(rendered) -> str:
	if isinstance(rendered, Group):
		return "\n".join(_renderable_str(part) for part in rendered.renderables)
	return rendered.code if isinstance(rendered, Syntax) else str(rendered)


async def test_partial_preview_is_swapped_for_the_durable_message():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		fake.feed(RunStarted(run_id="r1", seq=1))
		fake.feed(UserMessage(content="hello", seq=2))
		fake.feed(TextDelta(text="Mock "))
		fake.feed(TextDelta(text="reply"))
		fake.feed(ToolCallStarted(id="c1", name="edit"))  # no arguments yet: no text, no blank line
		fake.feed(TextDelta(text="after"))
		await pilot.pause()

		conversation = pilot.app.query_one(ConversationView)
		assert len(conversation.query(EntryView)) == 1  # the user message
		partial = conversation.query_one(PartialAssistantView)
		assert _widget_text(partial) == "Mock reply\nafter▌"

		fake.feed(AssistantMessage(content=[TextContent(text="Mock reply, final")], seq=3))
		fake.feed(RunEnded(seq=4))
		await pilot.pause()

		assert not conversation.query(PartialAssistantView)  # swapped, not appended
		entries = conversation.query(EntryView)
		assert len(entries) == 2
		assert "Mock reply, final" in _widget_text(entries.last())


async def test_tool_calls_and_results_render():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		fake.feed(RunStarted(run_id="r1", seq=1))
		fake.feed(
			AssistantMessage(content=[ToolCall(id="t1", name="bash", arguments={"command": "ls"})], seq=2)
		)
		await pilot.pause()

		conversation = pilot.app.query_one(ConversationView)
		view = conversation.query_one(ToolCallView)
		assert "bash ls" in _widget_text(view)  # per-tool one-liner, not a JSON dump

		content = "\n".join(f"file{i}" for i in range(6))
		fake.feed(
			ToolResult(tool_call_id="t1", name="bash", content=content, details={"exit_code": 0}, seq=3)
		)
		await pilot.pause()

		assert len(conversation.query(EntryView)) == 1  # result merged into the call, not appended
		text = _widget_text(view)
		assert "[exit 0]" in text and "file0" in text
		assert "file5" not in text and "+3 lines" in text  # collapsed preview

		# results whose call was never seen render from their details
		fake.feed(
			ToolResult(
				tool_call_id="t2",
				name="bash",
				content="$ ls\na.txt\n[exit code: 0]",
				details={
					"command": "ls",
					"exit_code": 0,
					"duration_seconds": 0.01,
					"truncation": {"truncated": False},
					"full_output_path": None,
				},
				seq=4,
			)
		)
		fake.feed(
			ToolResult(
				tool_call_id="t3",
				name="bash",
				content="$ yes\ny\n[output truncated]",
				details={
					"command": "yes",
					"exit_code": 1,
					"truncation": {"truncated": True, "output_lines": 2000, "total_lines": 90000},
				},
				is_error=True,
				seq=5,
			)
		)
		diff = "--- a/f.py\n+++ b/f.py\n-old line\n+new line"
		fake.feed(
			ToolResult(
				tool_call_id="t4",
				name="edit",
				content="edited f.py",
				details={"path": "/proj/f.py", "edits": 1, "diff": diff},
				seq=6,
			)
		)
		await pilot.pause()

		_, ok, failed, edit = conversation.query(EntryView)
		ok_text = _widget_text(ok)
		assert "bash ls" in ok_text and "[exit 0, 0.01s]" in ok_text and "a.txt" in ok_text
		failed_text = _widget_text(failed)
		assert (
			"✗" in failed_text and "exit 1" in failed_text and "truncated · 2000/90000 lines" in failed_text
		)
		edit_text = _widget_text(edit)
		assert "edit" in edit_text and "/proj/f.py" in edit_text and "1 edit" in edit_text
		assert "+new line" in edit_text
		rendered = edit.query_one(ToolCallView).render()
		rendered = getattr(rendered, "_renderable", rendered)
		assert isinstance(rendered, Group)  # diffs render by default, no expand needed
		assert any(isinstance(r, Syntax) and r.lexer.name.lower() == "diff" for r in rendered.renderables)

		await pilot.press("ctrl+o")
		await pilot.pause()
		assert "file5" in _widget_text(view)

		await pilot.press("ctrl+o")
		await pilot.pause()
		assert "file5" not in _widget_text(view)


async def test_thinking_folds_and_ctrl_t_toggles_it():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		fake.feed(
			AssistantMessage(
				content=[
					ThinkingContent(thinking="let me think"),
					TextContent(text="the answer"),
					ThinkingContent(thinking="secret", redacted=True),
				],
				seq=1,
			)
		)
		fake.feed(RunStarted(run_id="r1", seq=2))
		fake.feed(ThinkingDelta(thinking="hmm "))
		fake.feed(ThinkingDelta(thinking="okay"))
		fake.feed(TextDelta(text="reply"))
		await pilot.pause()

		conversation = pilot.app.query_one(ConversationView)
		entry = conversation.query(EntryView).last()
		blocks = entry.query(ThinkingBlock)
		assert len(blocks) == 1  # the redacted block is a sealed marker, not a foldable block
		block = blocks.first()
		assert block.collapsed is True
		text = _widget_text(entry)
		assert "let me think" not in text  # collapsed to its marker
		assert "the answer" in text
		assert "Thinking · redacted" in text and "secret" not in text
		partial = conversation.query_one(PartialAssistantView)
		preview = _widget_text(partial)
		assert THINKING_MARKER in preview and "hmm okay" not in preview and "reply" in preview

		await pilot.press("ctrl+t")
		await pilot.pause()
		assert block.collapsed is False
		assert "hmm okay" in _widget_text(partial)

		await pilot.press("ctrl+t")
		await pilot.pause()
		assert block.collapsed is True
		assert "hmm okay" not in _widget_text(partial)

		# entries that land after a toggle follow it
		await pilot.press("ctrl+t")
		fake.feed(AssistantMessage(content=[ThinkingContent(thinking="after toggle")], seq=3))
		await pilot.pause()
		assert conversation.query(EntryView).last().query_one(ThinkingBlock).collapsed is False


async def test_keys_submit_steer_abort_and_quit():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await pilot.press("h", "i", "enter")
		await pilot.pause()
		assert fake.calls == [("submit", "hi")]
		assert pilot.app.query_one(Composer).text == ""

		await pilot.press("escape")  # idle: nothing to abort, and escape never quits
		await pilot.pause()
		assert fake.calls == [("submit", "hi")]
		assert pilot.app.is_running

		fake.feed(RunStarted(run_id="r1", seq=1))
		fake.feed(UserMessage(content="hi", seq=2))
		await pilot.press("g", "o", "enter")
		await pilot.pause()
		assert fake.calls[-1] == ("submit", "go")  # server-side steering; app just sends

		await pilot.press("escape")
		await pilot.pause()
		assert fake.calls[-1] == ("abort",)

		await pilot.press("ctrl+d")  # quits, run or no run
		await pilot.pause()
		assert not pilot.app.is_running


async def test_alt_enter_queues_while_running():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		fake.feed(RunStarted(run_id="r1", seq=1))
		await pilot.press("q", "1", "alt+enter")
		await pilot.pause()
		assert fake.queued == ["q1"]
		assert fake.calls == []
		assert "1 queued" in _widget_text(pilot.app.query_one(StatusBar))


async def test_working_status_reserves_space_and_reports_elapsed_time():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		working = pilot.app.query_one("#working")
		spinner = working.query_one(Spinner)
		label = working.query_one("#working-label", Static)
		assert working.display is True
		assert working.styles.height.value == 3
		assert spinner.styles.visibility == "hidden"
		assert label.styles.visibility == "hidden"

		fake.feed(RunStarted(run_id="r1", seq=1))
		fake.feed(TextDelta(text="still working"))
		await pilot.pause()
		assert spinner.styles.visibility == "visible"
		assert label.styles.visibility == "visible"
		assert "Working..." in _widget_text(label)

		await pilot.pause(0.1)
		assert _widget_text(spinner) != SPINNER_FRAMES[0]

		fake.feed(RunEnded(seq=2))
		await pilot.pause()
		assert working.display is True
		assert spinner.styles.visibility == "hidden"
		assert "Worked for " in _widget_text(label)
		assert _widget_text(label).endswith(" seconds")


async def test_status_bar_reflects_state():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		fake.state.model = "mock"
		fake.feed(RunStarted(run_id="r1", seq=1))
		await pilot.pause()
		text = _widget_text(pilot.app.query_one(StatusBar))
		assert "mock" in text and "running" in text
		assert "fake-ses" not in text

		fake.feed(Usage(input_tokens=10, output_tokens=5, cost=0.5, context_window=256_000, seq=2))
		fake.feed(RunEnded(seq=3))
		await pilot.pause()
		text = _widget_text(pilot.app.query_one(StatusBar))
		assert "idle" in text and "15/256k" in text and "↑10" in text and "↓5" in text
		assert "$" not in text


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


async def test_integration_conversation_and_resume_over_live_server(tmp_path):
	async with _live_server(tmp_path) as url:
		config = SessionConfig(model="mock", cwd=str(tmp_path), auto_approve=True)
		async with FlowClient(url) as setup:
			other_sid = await setup.create_session(config)
			await setup.run(other_sid, "hello from the other side", wait=True)

		controller = Controller(FlowClient(url), config=config)
		async with FlowApp(controller).run_test() as pilot:
			async with asyncio.timeout(5):
				while controller.session_id is None:
					await pilot.pause(0.05)
			assert controller.session_id != other_sid

			await pilot.press("h", "i", "enter")
			conversation = pilot.app.query_one(ConversationView)

			def shows(text):
				return any(text in _widget_text(e) for e in conversation.query(EntryView))

			async with asyncio.timeout(10):
				while not shows("Mock reply to: hi"):
					await pilot.pause(0.05)

			assert not controller.state.running
			assert "idle" in _widget_text(pilot.app.query_one(StatusBar))

			# /resume tears the stream down, resets state, and replays the other session
			pilot.app.query_one(Composer).load_text(f"/resume {other_sid[:8]}")
			await pilot.press("enter")
			async with asyncio.timeout(10):
				while not shows("hello from the other side"):
					await pilot.pause(0.05)

			assert controller.session_id == other_sid
			assert any(isinstance(entry, UserMessage) for entry in controller.state.entries)
