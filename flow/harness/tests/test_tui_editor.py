"""Phase 11: external editor. Unit tests cover `edit_text_via_editor` with a script
editor and a stubbed suspend context; pilot tests cover chord arming/disarming and
the app-level guards (no editor configured, suspend unsupported)."""

import asyncio
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path

import pytest

from flow_tui import app as app_module
from flow_tui.app import FlowApp, edit_text_via_editor, resolve_editor
from flow_tui.client.state import Change, ConversationState, StatusChanged
from flow_tui.widgets.composer import Composer

# an "editor" that appends a line to the file it is given; the trailing `sh` makes
# the path land in $1, as the plan's example intends
SCRIPT_EDITOR = "sh -c 'echo edited >> \"$1\"' sh"


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


def test_editor_round_trip_runs_inside_suspend():
	entered = []

	@contextmanager
	def suspend():
		entered.append(True)
		yield

	result = edit_text_via_editor("draft\n", SCRIPT_EDITOR, suspend)
	assert result == "draft\nedited\n"
	assert entered == [True]


def test_editor_temp_file_is_removed(tmp_path):
	@contextmanager
	def suspend():
		yield

	# the editor leaks the draft path into a capture file so the test can check it
	capture = tmp_path / "seen-path"
	editor = f'sh -c \'echo "$1" > "{capture}"\' sh'
	edit_text_via_editor("x", editor, suspend)
	draft_path = Path(capture.read_text().strip())
	assert draft_path.suffix == ".md"
	assert not draft_path.exists()


def test_editor_temp_file_removed_even_when_suspend_raises(monkeypatch, tmp_path):
	import tempfile

	monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))

	@contextmanager
	def suspend():
		raise RuntimeError("no tty")
		yield

	with pytest.raises(RuntimeError):
		edit_text_via_editor("x", SCRIPT_EDITOR, suspend)
	assert list(tmp_path.iterdir()) == []


def test_resolve_editor_prefers_visual(monkeypatch):
	monkeypatch.setenv("VISUAL", "code -w")
	monkeypatch.setenv("EDITOR", "vim")
	assert resolve_editor() == "code -w"
	monkeypatch.delenv("VISUAL")
	assert resolve_editor() == "vim"
	monkeypatch.delenv("EDITOR")
	assert resolve_editor() is None


# --- chord arming under the pilot --------------------------------------------


async def test_ctrl_x_ctrl_e_requests_edit(monkeypatch):
	monkeypatch.delenv("VISUAL", raising=False)
	monkeypatch.setenv("EDITOR", "true")
	calls = []
	monkeypatch.setattr(
		app_module,
		"edit_text_via_editor",
		lambda text, editor, suspend: calls.append((text, editor)) or "edited draft",
	)
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await pilot.press("h", "i")
		await pilot.press("ctrl+x", "ctrl+e")
		await pilot.pause()
		assert calls == [("hi", "true")]
		assert pilot.app.query_one(Composer).text == "edited draft"


async def test_chord_disarms_on_other_key(monkeypatch):
	monkeypatch.delenv("VISUAL", raising=False)
	monkeypatch.setenv("EDITOR", "true")
	calls = []
	monkeypatch.setattr(app_module, "edit_text_via_editor", lambda *a: calls.append(a) or "")
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		composer = pilot.app.query_one(Composer)
		await pilot.press("ctrl+x")
		assert composer.chord_armed
		await pilot.press("a")
		assert not composer.chord_armed
		await pilot.press("ctrl+e")  # bare ctrl+e is just a TextArea key, not the chord
		await pilot.pause()
		assert calls == []
		assert composer.text == "a"


async def test_chord_disarms_after_timeout(monkeypatch):
	monkeypatch.setattr("flow_tui.widgets.composer.CHORD_TIMEOUT", 0.3)
	monkeypatch.delenv("VISUAL", raising=False)
	monkeypatch.setenv("EDITOR", "true")
	calls = []
	monkeypatch.setattr(app_module, "edit_text_via_editor", lambda *a: calls.append(a) or "")
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		composer = pilot.app.query_one(Composer)
		await pilot.press("ctrl+x")
		assert composer.chord_armed
		await pilot.pause(0.6)
		assert not composer.chord_armed
		await pilot.press("ctrl+e")
		await pilot.pause()
		assert calls == []


async def test_no_editor_configured_shows_hint(monkeypatch):
	monkeypatch.delenv("VISUAL", raising=False)
	monkeypatch.delenv("EDITOR", raising=False)
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await pilot.press("ctrl+x", "ctrl+e")
		await pilot.pause()
		assert any(
			"set $VISUAL or $EDITOR" in msg and sev == "warning" for msg, sev in _notifications(pilot.app)
		)


async def test_headless_suspend_shows_error(monkeypatch):
	# the pilot's headless driver cannot suspend, so the real helper raises
	# SuspendNotSupported — the app must toast, not crash
	monkeypatch.delenv("VISUAL", raising=False)
	monkeypatch.setenv("EDITOR", "true")
	fake = FakeController()
	async with FlowApp(fake).run_test() as pilot:
		await pilot.press("ctrl+x", "ctrl+e")
		await pilot.pause()
		assert any("real terminal" in msg and sev == "error" for msg, sev in _notifications(pilot.app))
