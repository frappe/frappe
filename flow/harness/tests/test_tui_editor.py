"""Phase 11: external editor. A unit test covers `edit_text_via_editor` with a script
editor and a stubbed suspend context; pilot tests cover chord arming/disarming and
the app-level guards (no editor configured, suspend unsupported)."""

import asyncio
import tempfile
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path

import pytest

from flow_tui import app as app_module
from flow_tui.app import FlowApp, edit_text_via_editor
from flow_tui.client.state import Change, ConversationState, StatusChanged
from flow_tui.widgets.composer import Composer


class FakeController:
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
		return "started"

	def queue(self, text):
		self.queued.append(text)

	async def abort(self):
		self.calls.append(("abort",))

	async def stop(self):
		pass


def _notifications(app) -> list[tuple[str, str]]:
	return [(n.message, n.severity) for n in app._notifications]


# --- edit_text_via_editor ----------------------------------------------------


def test_editor_round_trip_removes_its_draft_file(monkeypatch, tmp_path):
	drafts = tmp_path / "drafts"
	drafts.mkdir()
	monkeypatch.setattr(tempfile, "tempdir", str(drafts))
	# an "editor" that leaks the draft path to a capture file and appends a line to
	# the draft; the trailing `sh` makes the path land in $1
	capture = tmp_path / "seen-path"
	editor = f'sh -c \'echo "$1" > "{capture}"; echo edited >> "$1"\' sh'
	entered = []

	@contextmanager
	def suspend():
		entered.append(True)
		yield

	assert edit_text_via_editor("draft\n", editor, suspend) == "draft\nedited\n"
	assert entered == [True]
	draft_path = Path(capture.read_text().strip())
	assert draft_path.suffix == ".md"
	assert not draft_path.exists()

	@contextmanager
	def failing_suspend():
		raise RuntimeError("no tty")
		yield

	with pytest.raises(RuntimeError):
		edit_text_via_editor("x", editor, failing_suspend)
	assert list(drafts.iterdir()) == []


# --- chord arming under the pilot --------------------------------------------


async def test_ctrl_x_ctrl_e_chord_opens_the_editor(monkeypatch):
	monkeypatch.setattr("flow_tui.widgets.composer.CHORD_TIMEOUT", 0.3)
	monkeypatch.setenv("VISUAL", "true")
	monkeypatch.setenv("EDITOR", "vim")
	calls = []
	monkeypatch.setattr(
		app_module,
		"edit_text_via_editor",
		lambda text, editor, suspend: calls.append((text, editor)) or "edited draft",
	)
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		composer = pilot.app.query_one(Composer)
		# another key disarms the chord; a bare ctrl+e is just a TextArea key
		await pilot.press("ctrl+x")
		assert composer.chord_armed
		await pilot.press("a")
		assert not composer.chord_armed
		await pilot.press("ctrl+e")
		await pilot.pause()
		assert calls == []
		assert composer.text == "a"

		# so does the timeout
		await pilot.press("ctrl+x")
		assert composer.chord_armed
		await pilot.pause(0.6)
		assert not composer.chord_armed
		await pilot.press("ctrl+e")
		await pilot.pause()
		assert calls == []

		await pilot.press("ctrl+x", "ctrl+e")
		await pilot.pause()
		assert calls == [("a", "true")]  # $VISUAL wins over $EDITOR
		assert composer.text == "edited draft"


async def test_editor_guards_toast_instead_of_failing(monkeypatch):
	monkeypatch.delenv("VISUAL", raising=False)
	monkeypatch.delenv("EDITOR", raising=False)
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await pilot.press("ctrl+x", "ctrl+e")
		await pilot.pause()
		assert any(
			"set $VISUAL or $EDITOR" in msg and sev == "warning" for msg, sev in _notifications(pilot.app)
		)

		# the pilot's headless driver cannot suspend, so the real helper raises
		# SuspendNotSupported — the app must toast, not crash
		monkeypatch.setenv("EDITOR", "true")
		await pilot.press("ctrl+x", "ctrl+e")
		await pilot.pause()
		assert any("real terminal" in msg and sev == "error" for msg, sev in _notifications(pilot.app))
