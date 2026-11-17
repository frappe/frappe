"""Phase 9: model and effort pickers.

All tests run under the pilot with a fake controller feeding a canned `/models`
payload. The 409 path fakes `set_model` rejection with `FlowAPIError` and asserts
the toast — the status bar itself only moves on the durable `model_changed` event,
which the state-reducer tests already cover.
"""

import asyncio
from collections.abc import Callable

from textual.widgets import OptionList

from flow_harness.events import ModelChanged, ReasoningEffort
from flow_tui.app import FlowApp
from flow_tui.client.api import FlowAPIError
from flow_tui.client.state import Change, ConversationState, StatusChanged
from flow_tui.screens.pickers import EffortPicker, ModelPicker, SessionPicker
from flow_tui.widgets.composer import Composer
from flow_tui.widgets.status_bar import StatusBar

MODELS = [
	{"name": "anthropic/claude-sonnet-4", "provider": "anthropic"},
	{"name": "anthropic/claude-haiku-4", "provider": "anthropic"},
	{"name": "codex/gpt-5", "provider": "codex"},
]


class FakeController:
	def __init__(self):
		self.state = ConversationState()
		self.queued: list[str] = []
		self.steered_seqs: set[int] = set()
		self.session_id: str | None = "fake-session-id"
		self.on_changes: Callable[[list[Change]], None] = lambda changes: None
		self.calls = []
		self.models = MODELS
		self.sessions: list[dict] = []
		self.errors: list[str] = []
		self.set_model_error: FlowAPIError | None = None

	async def connect(self):
		self.on_changes([StatusChanged()])

	async def stream_events(self):
		await asyncio.Event().wait()

	async def submit(self, text):
		return "started"

	def queue(self, text):
		self.queued.append(text)

	async def abort(self):
		pass

	async def stop(self):
		pass

	async def change_model(self, model: str):
		if self.set_model_error is not None:
			raise self.set_model_error
		self.calls.append(("change_model", model))

	async def change_effort(self, effort: ReasoningEffort | None):
		if self.set_model_error is not None:
			raise self.set_model_error
		self.calls.append(("change_effort", effort))

	async def rewind(self, target_seq: int):
		pass

	async def list_sessions(self):
		return self.sessions

	async def list_models(self):
		return {"models": self.models, "errors": self.errors}

	async def new_session(self):
		return "new-session-id"

	async def switch_session(self, sid: str):
		self.calls.append(("switch_session", sid))

	def feed(self, event):
		changes = self.state.apply(event)
		if changes:
			self.on_changes(changes)


def _notifications(app) -> list[tuple[str, str]]:
	return [(str(n.message), n.severity) for n in app._notifications]


async def _slash(pilot, line: str) -> None:
	pilot.app.query_one(Composer).load_text(line)
	await pilot.press("enter")
	await pilot.pause()


async def _open_picker(pilot, line: str, kind) -> None:
	await _slash(pilot, line)
	async with asyncio.timeout(5):
		while not isinstance(pilot.app.screen, kind):
			await pilot.pause(0.05)


# --- model picker ------------------------------------------------------------


async def test_model_picker_selects_filters_and_cancels():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await _open_picker(pilot, "/model", ModelPicker)
		options = pilot.app.screen.query_one(OptionList)
		assert options.option_count == len(MODELS)
		assert [options.get_option_at_index(index).prompt for index in range(options.option_count)] == [
			model["name"] for model in MODELS
		]
		assert options.highlighted == 0

		await pilot.press("down", "enter")
		await pilot.pause()
		assert fake.calls == [("change_model", "anthropic/claude-haiku-4")]
		assert not isinstance(pilot.app.screen, ModelPicker)

		await _open_picker(pilot, "/model", ModelPicker)
		await pilot.press(*"codex")
		await pilot.pause()
		options = pilot.app.screen.query_one(OptionList)
		assert options.option_count == 1
		assert options.highlighted == 0
		await pilot.press("enter")
		await pilot.pause()
		chosen = [("change_model", "anthropic/claude-haiku-4"), ("change_model", "codex/gpt-5")]
		assert fake.calls == chosen

		# no free text: enter with nothing matching cancels, as does escape
		await _open_picker(pilot, "/model", ModelPicker)
		await pilot.press(*"zzz")
		await pilot.pause()
		assert pilot.app.screen.query_one(OptionList).option_count == 0
		await pilot.press("enter")
		await pilot.pause()
		assert not isinstance(pilot.app.screen, ModelPicker)

		await _open_picker(pilot, "/model", ModelPicker)
		await pilot.press("escape")
		await pilot.pause()
		assert not isinstance(pilot.app.screen, ModelPicker)
		assert fake.calls == chosen


# --- session picker ----------------------------------------------------------

SESSIONS = [
	{"session_id": "fake-session-id", "state": "idle", "model": "mock", "latest_seq": 4, "cwd": "/a"},
	{"session_id": "0ther-session-id", "state": "idle", "model": "codex/gpt-5", "latest_seq": 9, "cwd": "/b"},
]


async def test_session_picker_switches_and_cancels():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await _slash(pilot, "/resume")
		assert fake.calls == []
		assert any("no sessions" in msg for msg, _ in _notifications(pilot.app))

		fake.sessions = SESSIONS
		await _open_picker(pilot, "/resume", SessionPicker)
		options = pilot.app.screen.query_one(OptionList)
		assert options.option_count == len(SESSIONS)
		assert "current" in options.get_option_at_index(0).prompt
		await pilot.press("escape")
		await pilot.pause()
		assert fake.calls == []
		assert not isinstance(pilot.app.screen, SessionPicker)

		await _open_picker(pilot, "/resume", SessionPicker)
		await pilot.press(*"codex")
		await pilot.pause()
		assert pilot.app.screen.query_one(OptionList).option_count == 1
		await pilot.press("enter")
		await pilot.pause()
		assert fake.calls == [("switch_session", "0ther-session-id")]
		assert not isinstance(pilot.app.screen, SessionPicker)


# --- effort picker -----------------------------------------------------------


async def test_effort_picker_starts_on_the_current_level():
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await _open_picker(pilot, "/effort", EffortPicker)
		options = pilot.app.screen.query_one(OptionList)
		# no effort set → "default" starts highlighted, and maps to None
		assert options.highlighted == options.get_option_index("default")
		await pilot.press("enter")
		await pilot.pause()
		assert fake.calls == [("change_effort", None)]

		fake.state.reasoning_effort = "medium"
		await _open_picker(pilot, "/effort", EffortPicker)
		options = pilot.app.screen.query_one(OptionList)
		assert options.highlighted == options.get_option_index("medium")
		await pilot.press("escape")
		await pilot.pause()
		assert fake.calls == [("change_effort", None)]

		await _open_picker(pilot, "/effort", EffortPicker)
		options = pilot.app.screen.query_one(OptionList)
		options.highlighted = options.get_option_index("high")
		await pilot.press("enter")
		await pilot.pause()
		assert fake.calls == [("change_effort", None), ("change_effort", "high")]


# --- 409 mid-run and durable status updates ----------------------------------


async def test_status_bar_moves_only_on_the_durable_model_change():
	fake = FakeController()
	fake.state.model = "mock"
	fake.set_model_error = FlowAPIError(409, "a run is active")
	async with FlowApp(fake).run_test() as pilot:
		await _open_picker(pilot, "/model", ModelPicker)
		await pilot.press("enter")
		await pilot.pause()
		assert any("a run is active" in msg and sev == "error" for msg, sev in _notifications(pilot.app))
		# no optimistic update: the bar still shows the old model
		assert "mock" in str(pilot.app.query_one(StatusBar).render())

		fake.feed(ModelChanged(model="codex/gpt-5", reasoning_effort="high", seq=7))
		await pilot.pause()
		bar = str(pilot.app.query_one(StatusBar).render())
		assert "codex/gpt-5" in bar and "high" in bar
