"""Phase 8: command registry, slash dispatch from the composer, and the palette.

Registry parsing is plain unit tests; dispatch and the palette run under the pilot
with a fake controller. One live-server test covers `/resume` switching end to
end — stream teardown, state reset, history replay on the new session.
"""

import asyncio
import socket
from collections.abc import Callable
from contextlib import asynccontextmanager

import pytest
import uvicorn
from textual.command import CommandPalette
from textual.widgets import Input, Static

from flow.events import AssistantMessage, ReasoningEffort, RunStarted, TextContent, UserMessage
from flow.model.credentials import CredentialStore
from flow.server import create_app
from flow.session.config import SessionConfig
from flow.session.store import SessionStore
from flow_tui.app import FlowApp
from flow_tui.client.api import FlowAPIError, FlowClient
from flow_tui.client.state import Change, ConversationState, StatusChanged
from flow_tui.commands import REGISTRY, CommandError, parse
from flow_tui.controller import Controller
from flow_tui.widgets.composer import Composer
from flow_tui.widgets.conversation import ConversationView
from flow_tui.widgets.messages import EntryView


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


# --- registry ---------------------------------------------------------------


def test_registry_has_the_initial_command_set():
	assert set(REGISTRY) == {
		"model",
		"effort",
		"abort",
		"rewind",
		"new",
		"clear",
		"resume",
		"reload",
		"editor",
		"help",
		"quit",
	}


def test_parse_splits_command_and_arg():
	found, arg = parse("/rewind 5")
	assert found is REGISTRY["rewind"]
	assert arg == "5"
	found, arg = parse("/abort")
	assert found is REGISTRY["abort"] and arg == ""


def test_parse_rejects_unknown_command():
	with pytest.raises(CommandError, match="unknown command: /nope"):
		parse("/nope")


# --- slash dispatch under the pilot -----------------------------------------


async def test_slash_abort_reaches_controller_and_is_not_a_message():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await _slash(pilot, "/abort")
		assert fake.calls == [("abort",)]
		assert pilot.app.query_one(Composer).text == ""


async def test_skill_directive_is_submitted_to_the_server():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await _slash(pilot, "/skill:testing add parser tests")
		assert fake.calls == [("submit", "/skill:testing add parser tests")]


async def test_alt_enter_queues_skill_directive_while_running():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		fake.feed(RunStarted(run_id="r1", seq=1))
		pilot.app.query_one(Composer).load_text("/skill:testing later")
		await pilot.press("alt+enter")
		await pilot.pause()

		assert fake.queued == ["/skill:testing later"]
		assert fake.calls == []


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


async def test_unknown_command_shows_inline_error():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await _slash(pilot, "/nope")
		assert fake.calls == []
		assert any(
			"unknown command: /nope" in msg and sev == "error" for msg, sev in _notifications(pilot.app)
		)


async def test_slash_is_a_command_even_while_running():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		fake.feed(RunStarted(run_id="r1", seq=1))
		await _slash(pilot, "/abort")
		assert fake.calls == [("abort",)]
		assert fake.queued == []


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


async def test_rewind_with_seq_and_default_to_before_last_user_message():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		fake.feed(UserMessage(content="first", seq=2))
		fake.feed(AssistantMessage(content=[TextContent(text="reply one")], seq=3))
		fake.feed(UserMessage(content="second question", seq=5))
		fake.feed(AssistantMessage(content=[TextContent(text="reply two")], seq=6))

		await _slash(pilot, "/rewind 2")
		assert fake.calls == [("rewind", 2)]

		await _slash(pilot, "/rewind")
		assert fake.calls[-1] == ("rewind", 3)
		# the dropped user message comes back to the composer for a rephrase
		assert pilot.app.query_one(Composer).text == "second question"


async def test_rewind_restores_concise_skill_command():
	fake = FakeController()
	expanded = (
		'<skill name="testing" location="/skills/testing/SKILL.md">\n'
		"References are relative to /skills/testing.\n\n"
		"Run tests.\n"
		"</skill>\n\nfocus parser coverage"
	)
	async with FlowApp(fake).run_test() as pilot:
		fake.feed(
			UserMessage(
				content=expanded,
				seq=2,
			)
		)
		await _slash(pilot, "/rewind")

		assert pilot.app.query_one(Composer).text == "/skill:testing focus parser coverage"


async def test_rewind_default_with_no_user_message_errors():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await _slash(pilot, "/rewind")
		assert fake.calls == []
		assert any("nothing to rewind" in msg for msg, _ in _notifications(pilot.app))


async def test_resume_switches_by_prefix():
	fake = FakeController()
	fake.sessions = [
		{"session_id": "fake-session-id", "state": "idle", "model": "mock", "latest_seq": 4, "cwd": "/a"},
		{"session_id": "0ther-session-id", "state": "idle", "model": "mock", "latest_seq": 9, "cwd": "/b"},
	]
	async with FlowApp(fake).run_test() as pilot:
		await _slash(pilot, "/resume 0ther")
		assert fake.calls == [("switch_session", "0ther-session-id")]

		await _slash(pilot, "/resume missing")
		assert any("no session matches" in msg for msg, _ in _notifications(pilot.app))
		await _slash(pilot, "/resume fake")
		assert any("already on that session" in msg for msg, _ in _notifications(pilot.app))
		assert fake.calls == [("switch_session", "0ther-session-id")]


@pytest.mark.parametrize("command", ["new", "clear"])
async def test_new_command_creates_and_announces(command):
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await _slash(pilot, f"/{command}")
		assert fake.calls == [("new_session",)]
		assert any("new session new-sess" in msg for msg, _ in _notifications(pilot.app))


async def test_help_lists_every_command():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await _slash(pilot, "/help")
		listing = next(msg for msg, _ in _notifications(pilot.app))
		assert all(f"/{name}" in listing for name in REGISTRY)


async def test_quit_exits_the_app():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
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


# --- live switching over a real server --------------------------------------


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


async def test_integration_resume_switch_replays_other_session(tmp_path):
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
			first_sid = controller.session_id
			assert first_sid != other_sid

			await _slash(pilot, f"/resume {other_sid[:8]}")
			conversation = pilot.app.query_one(ConversationView)

			def replayed():
				entries = conversation.query(EntryView)
				texts = [str(static.render()) for e in entries for static in e.query(Static)]
				return any("hello from the other side" in text for text in texts)

			async with asyncio.timeout(10):
				while not replayed():
					await pilot.pause(0.05)

			assert controller.session_id == other_sid
			assert any(isinstance(entry, UserMessage) for entry in controller.state.entries)
