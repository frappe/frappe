"""Phase 8: slash dispatch from the composer, and the command palette.

Dispatch and the palette run under the pilot with a fake controller; the live-server
test in `test_tui_shell.py` covers `/resume` switching end to end.
"""

import asyncio
from collections.abc import Callable

from textual.command import CommandPalette
from textual.widgets import Input

from flow_harness.events import AssistantMessage, ReasoningEffort, RunStarted, TextContent, UserMessage
from flow_tui.app import FlowApp
from flow_tui.client.api import FlowAPIError
from flow_tui.client.state import Change, ConversationState, StatusChanged
from flow_tui.commands import REGISTRY
from flow_tui.controller import Controller
from flow_tui.widgets.composer import Composer


class FakeController:
	def __init__(self):
		self.state = ConversationState()
		self.queued: list[str] = []
		self.steered_seqs: set[int] = set()
		self.session_id: str | None = "fake-session-id"
		self.on_changes: Callable[[list[Change]], None] = lambda changes: None
		self.calls = []
		self.sessions: list[dict] = []

	async def connect(self):
		self.on_changes([StatusChanged()])

	async def stream_events(self):
		await asyncio.Event().wait()

	async def submit(self, text):
		self.calls.append(("submit", text))
		return "started"

	def queue(self, text):
		self.queued.append(text)

	async def abort(self):
		self.calls.append(("abort",))

	async def stop(self):
		pass

	async def change_model(self, model: str):
		self.calls.append(("change_model", model))

	async def change_effort(self, effort: ReasoningEffort | None):
		self.calls.append(("change_effort", effort))

	async def rewind(self, target_seq: int):
		self.calls.append(("rewind", target_seq))

	async def list_sessions(self):
		return self.sessions

	async def list_models(self):
		return {"models": [], "errors": []}

	async def new_session(self):
		self.calls.append(("new_session",))
		return "new-session-id"

	async def switch_session(self, sid: str):
		self.calls.append(("switch_session", sid))

	def feed(self, event):
		changes = self.state.apply(event)
		if changes:
			self.on_changes(changes)


def _notifications(app) -> list[tuple[str, str]]:
	return [(n.message, n.severity) for n in app._notifications]


async def _slash(pilot, line: str) -> None:
	pilot.app.query_one(Composer).load_text(line)
	await pilot.press("enter")
	await pilot.pause()


# --- slash dispatch under the pilot -----------------------------------------


async def test_slash_lines_are_commands_and_skill_directives_are_prompts():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await _slash(pilot, "/abort")
		assert fake.calls == [("abort",)]
		assert pilot.app.query_one(Composer).text == ""

		await _slash(pilot, "/nope")
		assert fake.calls == [("abort",)]
		assert any(
			"unknown command: /nope" in msg and sev == "error" for msg, sev in _notifications(pilot.app)
		)

		await _slash(pilot, "/skill:testing add parser tests")
		assert fake.calls == [("abort",), ("submit", "/skill:testing add parser tests")]

		# while running, a slash line is still a command and alt+enter queues a skill directive
		fake.feed(RunStarted(run_id="r1", seq=1))
		await _slash(pilot, "/abort")
		calls = [("abort",), ("submit", "/skill:testing add parser tests"), ("abort",)]
		assert fake.calls == calls
		assert fake.queued == []

		pilot.app.query_one(Composer).load_text("/skill:testing later")
		await pilot.press("alt+enter")
		await pilot.pause()
		assert fake.queued == ["/skill:testing later"]
		assert fake.calls == calls


async def test_rejected_queued_skill_does_not_escape_the_controller():
	class RejectingClient:
		def __init__(self):
			self.messages = []

		async def run(self, sid, message):
			self.messages.append(message)
			if message == "/skill:missing":
				raise FlowAPIError(400, "unknown skill: missing")
			return {"status": "started"}

	client = RejectingClient()
	controller = Controller(client, session_id="session-1")  # type: ignore[arg-type]
	errors = []
	controller.on_error = errors.append
	controller.queue("/skill:missing")
	controller.queue("continue")

	await controller._flush_queue()

	assert controller.queued == []
	assert client.messages == ["/skill:missing", "continue"]
	assert [error.detail for error in errors] == ["unknown skill: missing"]


async def test_model_and_effort_commands():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await _slash(pilot, "/model openai/gpt-x")
		await _slash(pilot, "/effort high")
		await _slash(pilot, "/effort default")
		assert fake.calls == [
			("change_model", "openai/gpt-x"),
			("change_effort", "high"),
			("change_effort", None),
		]

		await _slash(pilot, "/effort bogus")
		assert fake.calls[-1] == ("change_effort", None)  # the bad line did not dispatch
		errors = [msg for msg, sev in _notifications(pilot.app) if sev == "error"]
		assert any("usage: /effort" in msg for msg in errors)


async def test_rewind_command():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await _slash(pilot, "/rewind")
		assert fake.calls == []
		assert any("nothing to rewind" in msg for msg, _ in _notifications(pilot.app))

		fake.feed(UserMessage(content="first", seq=2))
		fake.feed(AssistantMessage(content=[TextContent(text="reply one")], seq=3))
		fake.feed(UserMessage(content="second question", seq=5))
		fake.feed(AssistantMessage(content=[TextContent(text="reply two")], seq=6))

		await _slash(pilot, "/rewind 2")
		assert fake.calls == [("rewind", 2)]

		# no seq: back to before the last user message
		await _slash(pilot, "/rewind")
		assert fake.calls[-1] == ("rewind", 3)
		# the dropped user message comes back to the composer for a rephrase
		assert pilot.app.query_one(Composer).text == "second question"

		# a skill prompt comes back as its concise command
		expanded = (
			'<skill name="testing" location="/skills/testing/SKILL.md">\n'
			"References are relative to /skills/testing.\n\n"
			"Run tests.\n"
			"</skill>\n\nfocus parser coverage"
		)
		fake.feed(UserMessage(content=expanded, seq=7))
		await _slash(pilot, "/rewind")
		assert fake.calls[-1] == ("rewind", 6)
		assert pilot.app.query_one(Composer).text == "/skill:testing focus parser coverage"


async def test_new_and_resume_commands():
	fake = FakeController()
	fake.sessions = [
		{"session_id": "fake-session-id", "state": "idle", "model": "mock", "latest_seq": 4, "cwd": "/a"},
		{"session_id": "0ther-session-id", "state": "idle", "model": "mock", "latest_seq": 9, "cwd": "/b"},
	]
	async with FlowApp(fake).run_test() as pilot:
		for count, command in enumerate(["new", "clear"], start=1):
			await _slash(pilot, f"/{command}")
			assert fake.calls == [("new_session",)] * count, command
			announced = [msg for msg, _ in _notifications(pilot.app) if "new session new-sess" in msg]
			assert len(announced) == count, command

		await _slash(pilot, "/resume 0ther")
		assert fake.calls[2:] == [("switch_session", "0ther-session-id")]

		await _slash(pilot, "/resume missing")
		assert any("no session matches" in msg for msg, _ in _notifications(pilot.app))
		await _slash(pilot, "/resume fake")
		assert any("already on that session" in msg for msg, _ in _notifications(pilot.app))
		assert fake.calls[2:] == [("switch_session", "0ther-session-id")]


async def test_help_lists_every_command_and_quit_exits():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await _slash(pilot, "/help")
		listing = next(msg for msg, _ in _notifications(pilot.app))
		assert all(f"/{name}" in listing for name in REGISTRY)

		await _slash(pilot, "/quit")
		assert pilot.app._exit


# --- palette ----------------------------------------------------------------


async def test_palette_opens_and_runs_a_command():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await pilot.press("ctrl+p")
		await pilot.pause()
		assert isinstance(pilot.app.screen, CommandPalette)
		assert pilot.app.screen.query_one(Input).placeholder == "filter commands"
		assert pilot.app.screen.query_one("SearchIcon").styles.display == "none"

		await pilot.press(*"abort")
		await pilot.pause()
		await pilot.press("down", "enter")
		await pilot.pause()
		assert ("abort",) in fake.calls
		assert not isinstance(pilot.app.screen, CommandPalette)
