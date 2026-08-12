"""Prompt history navigation in the composer and history collection across sessions."""

import asyncio
from collections.abc import Callable

from flow_tui.app import FlowApp
from flow_tui.client.state import Change, ConversationState, StatusChanged
from flow_tui.controller import Controller
from flow_tui.widgets.composer import Composer


class FakeController:
	def __init__(self, history: list[str]):
		self.state = ConversationState()
		self.queued: list[str] = []
		self.steered_seqs: set[int] = set()
		self.session_id: str | None = "current"
		self.on_changes: Callable[[list[Change]], None] = lambda changes: None
		self.history = history
		self.submitted: list[str] = []

	async def connect(self):
		self.on_changes([StatusChanged()])

	async def prompt_history(self, limit: int = 100):
		return self.history[-limit:]

	async def stream_events(self):
		await asyncio.Event().wait()

	async def submit(self, text):
		self.submitted.append(text)
		return "started"

	def queue(self, text):
		self.queued.append(text)

	async def abort(self):
		pass

	async def stop(self):
		pass


async def test_up_browses_history_and_down_restores_draft():
	fake = FakeController(["older session", "first current", "latest current"])
	async with FlowApp(fake).run_test() as pilot:
		await pilot.pause()
		await pilot.press(*"draft")
		await pilot.press("up")
		assert pilot.app.query_one(Composer).text == "latest current"
		await pilot.press("up", "up")
		assert pilot.app.query_one(Composer).text == "older session"
		await pilot.press("up")
		assert pilot.app.query_one(Composer).text == "older session"
		await pilot.press("down", "down", "down")
		assert pilot.app.query_one(Composer).text == "draft"


async def test_submitted_prompt_is_available_immediately():
	fake = FakeController([])
	async with FlowApp(fake).run_test() as pilot:
		await pilot.press(*"new prompt", "enter")
		await pilot.pause()
		assert fake.submitted == ["new prompt"]
		await pilot.press("up")
		assert pilot.app.query_one(Composer).text == "new prompt"


async def test_submitted_skill_prompt_is_available_immediately():
	fake = FakeController([])
	async with FlowApp(fake).run_test() as pilot:
		composer = pilot.app.query_one(Composer)
		composer.load_text("/skill:review check auth")
		await pilot.press("enter")
		await pilot.pause()
		assert fake.submitted == ["/skill:review check auth"]
		await pilot.press("up")
		assert composer.text == "/skill:review check auth"


class HistoryClient:
	def __init__(self):
		self.entry_calls: list[tuple[str, str]] = []

	async def list_sessions(self):
		return [{"session_id": "previous"}, {"session_id": "current"}]

	async def entries(self, sid: str, *, since: int = 0, path: str = "active"):
		self.entry_calls.append((sid, path))
		entries = {
			"current": [
				{"type": "user_message", "content": "current one"},
				{"type": "assistant_message", "content": []},
				{"type": "user_message", "content": "current two"},
			],
			"previous": [
				{
					"type": "user_message",
					"content": (
						'<skill name="review" location="/skills/review/SKILL.md">\n'
						"References are relative to /skills/review.\n\n"
						"Review carefully.\n"
						"</skill>\n\ncheck auth"
					),
				},
				{"type": "user_message", "content": "previous two"},
			],
		}
		return {"entries": entries[sid]}


async def test_controller_collects_current_then_previous_session_history():
	client = HistoryClient()
	controller = Controller(client, session_id="current")  # type: ignore[arg-type]

	assert await controller.prompt_history() == [
		"/skill:review check auth",
		"previous two",
		"current one",
		"current two",
	]
	assert client.entry_calls == [("current", "all"), ("previous", "all")]
