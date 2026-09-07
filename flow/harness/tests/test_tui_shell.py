"""Phases 6-7 TUI shell: rendering, delta→durable swap, steering, queueing, status
bar, foldable thinking, and detail-driven tool-result rendering.

Pilot tests drive `FlowApp` with a fake controller (no HTTP); one integration test
runs the real stack — uvicorn + MockModel + Controller — end to end.
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


async def test_partial_tool_identity_is_invisible_without_adding_layout_space():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		fake.feed(RunStarted(run_id="r1", seq=1))
		fake.feed(TextDelta(text="before"))
		fake.feed(ToolCallStarted(id="c1", name="edit"))
		fake.feed(TextDelta(text="after"))
		await pilot.pause()

		partial = pilot.app.query_one(PartialAssistantView)
		assert _widget_text(partial) == "before\nafter▌"


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


async def test_tool_result_merges_into_call_and_ctrl_o_expands():
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

		await pilot.press("ctrl+o")
		await pilot.pause()
		assert "file5" in _widget_text(view)

		await pilot.press("ctrl+o")
		await pilot.pause()
		assert "file5" not in _widget_text(view)


async def test_thinking_collapsed_by_default_and_redacted_stays_sealed():
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
		await pilot.pause()

		entry = pilot.app.query_one(ConversationView).query(EntryView).last()
		blocks = entry.query(ThinkingBlock)
		assert len(blocks) == 1  # the redacted block is a sealed marker, not a foldable block
		assert blocks.first().collapsed is True
		text = _widget_text(entry)
		assert "let me think" not in text  # collapsed to its marker
		assert "the answer" in text
		assert "Thinking · redacted" in text and "secret" not in text


async def test_ctrl_t_toggles_thinking_blocks_and_partial():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		fake.feed(AssistantMessage(content=[ThinkingContent(thinking="pondering")], seq=1))
		fake.feed(RunStarted(run_id="r1", seq=2))
		fake.feed(ThinkingDelta(thinking="hmm "))
		fake.feed(ThinkingDelta(thinking="okay"))
		fake.feed(TextDelta(text="reply"))
		await pilot.pause()

		block = pilot.app.query_one(ThinkingBlock)
		partial = pilot.app.query_one(PartialAssistantView)
		assert block.collapsed is True
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


async def test_new_entries_honor_thinking_toggle():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await pilot.press("ctrl+t")
		fake.feed(AssistantMessage(content=[ThinkingContent(thinking="after toggle")], seq=1))
		await pilot.pause()
		assert pilot.app.query_one(ThinkingBlock).collapsed is False


async def test_bash_result_renders_status_suffix_and_collapsed_output():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		fake.feed(
			ToolResult(
				tool_call_id="t1",
				name="bash",
				content="$ ls\na.txt\n[exit code: 0]",
				details={
					"command": "ls",
					"exit_code": 0,
					"duration_seconds": 0.01,
					"truncation": {"truncated": False},
					"full_output_path": None,
				},
				seq=1,
			)
		)
		fake.feed(
			ToolResult(
				tool_call_id="t2",
				name="bash",
				content="$ yes\ny\n[output truncated]",
				details={
					"command": "yes",
					"exit_code": 1,
					"truncation": {"truncated": True, "output_lines": 2000, "total_lines": 90000},
				},
				is_error=True,
				seq=2,
			)
		)
		await pilot.pause()

		entries = pilot.app.query_one(ConversationView).query(EntryView)
		ok = _widget_text(entries.first())
		assert "bash ls" in ok and "[exit 0, 0.01s]" in ok and "a.txt" in ok
		failed = _widget_text(entries.last())
		assert "✗" in failed and "exit 1" in failed and "truncated · 2000/90000 lines" in failed


async def test_edit_result_renders_highlighted_diff():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		diff = "--- a/f.py\n+++ b/f.py\n-old line\n+new line"
		fake.feed(
			ToolResult(
				tool_call_id="t1",
				name="edit",
				content="edited f.py",
				details={"path": "/proj/f.py", "edits": 1, "diff": diff},
				seq=1,
			)
		)
		await pilot.pause()

		entry = pilot.app.query_one(ConversationView).query(EntryView).last()
		text = _widget_text(entry)
		assert "edit" in text and "/proj/f.py" in text and "1 edit" in text and "+new line" in text
		rendered = entry.query_one(ToolCallView).render()
		rendered = getattr(rendered, "_renderable", rendered)
		assert isinstance(rendered, Group)  # diffs render by default, no expand needed
		assert any(isinstance(r, Syntax) and r.lexer.name.lower() == "diff" for r in rendered.renderables)


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


async def test_escape_while_idle_does_not_exit():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await pilot.press("escape")
		await pilot.pause()
		assert fake.calls == []
		assert pilot.app.is_running


async def test_ctrl_d_exits():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await pilot.press("ctrl+d")
		await pilot.pause()
		assert not pilot.app.is_running


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
