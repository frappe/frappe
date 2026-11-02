"""FlowApp — the TUI shell: transcript, composer, status bar.

The app is a view over the controller: it routes `Change` notices from the reducer to
widgets and user input back to controller verbs. `run_app()` is the entry point used
by bare `flow` and `flow attach`.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import ClassVar, Protocol

from textual.app import App, ComposeResult, SuspendNotSupported
from textual.binding import Binding
from textual.command import CommandPalette
from textual.containers import Horizontal
from textual.widgets import Static

from flow_harness.config import UDS_URL
from flow_harness.events import ReasoningEffort
from flow_harness.session.config import SessionConfig
from flow_tui.client.api import FlowAPIError, FlowClient
from flow_tui.client.state import (
	ApprovalChanged,
	Change,
	ConversationState,
	EntriesTruncated,
	EntryAdded,
	EntryReplaced,
	PartialCleared,
	StatusChanged,
	StreamDelta,
)
from flow_tui.commands import FlowCommandProvider, dispatch
from flow_tui.controller import Controller
from flow_tui.theme import flow_theme
from flow_tui.widgets.composer import Composer
from flow_tui.widgets.conversation import ConversationView
from flow_tui.widgets.messages import SPINNER_FRAMES
from flow_tui.widgets.status_bar import StatusBar

TUI_SYSTEM_SUFFIX = (
	"## Client\n"
	"The user talks to you through the flow terminal UI. Keep answers terminal-friendly: "
	"plain text and fenced code blocks; no HTML."
)


class Spinner(Static):
	def __init__(self) -> None:
		super().__init__(SPINNER_FRAMES[0])
		self._frame = 0

	def on_mount(self) -> None:
		self.set_interval(0.08, self._advance)

	def _advance(self) -> None:
		self._frame = (self._frame + 1) % len(SPINNER_FRAMES)
		self.update(SPINNER_FRAMES[self._frame])


class WorkingStatus(Horizontal):
	def __init__(self) -> None:
		super().__init__(Spinner(), Static(" Working...", id="working-label"), id="working")
		self._started_at: float | None = None

	def on_mount(self) -> None:
		self.query_one(Spinner).styles.visibility = "hidden"
		self.query_one("#working-label").styles.visibility = "hidden"

	def set_running(self, running: bool) -> None:
		spinner = self.query_one(Spinner)
		label = self.query_one("#working-label", Static)
		if running:
			if self._started_at is None:
				self._started_at = time.monotonic()
			spinner.styles.visibility = "visible"
			label.styles.visibility = "visible"
			label.update(" Working...")
		elif self._started_at is not None:
			elapsed = time.monotonic() - self._started_at
			self._started_at = None
			spinner.styles.visibility = "hidden"
			label.styles.visibility = "visible"
			label.update(f" Worked for {elapsed:.1f} seconds")


def resolve_editor() -> str | None:
	"""The external editor command, `$VISUAL` over `$EDITOR`. The command must block
	until the edit is done (`vim`, `code -w`, …) — a forking editor returns an
	unchanged draft."""
	return os.environ.get("VISUAL") or os.environ.get("EDITOR") or None


def edit_text_via_editor(
	text: str,
	editor: str,
	suspend: Callable[[], AbstractContextManager[None]],
) -> str:
	"""Round-trip `text` through `editor` while the TUI is suspended."""
	with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
		handle.write(text)
		path = Path(handle.name)
	try:
		with suspend():
			subprocess.run([*shlex.split(editor), str(path)], check=False)
		return path.read_text(encoding="utf-8")
	finally:
		path.unlink(missing_ok=True)


class ControllerLike(Protocol):
	"""What the app needs from a controller — a seam so pilot tests can fake it."""

	state: ConversationState
	queued: list[str]
	steered_seqs: set[int]
	session_id: str | None
	on_changes: Callable[[list[Change]], None]
	on_error: Callable[[FlowAPIError], None]

	async def connect(self) -> None: ...
	async def stream_events(self) -> None: ...
	async def submit(self, text: str) -> str: ...
	def queue(self, text: str) -> None: ...
	async def abort(self) -> None: ...
	async def stop(self) -> None: ...
	async def change_model(self, model: str) -> None: ...
	async def change_effort(self, effort: ReasoningEffort | None) -> None: ...
	async def rewind(self, target_seq: int) -> None: ...
	async def list_sessions(self) -> list[dict]: ...
	async def list_models(self) -> dict: ...
	async def reload_extensions(self) -> dict: ...
	async def prompt_history(self, limit: int = 100) -> list[str]: ...
	async def new_session(self) -> str: ...
	async def switch_session(self, sid: str) -> None: ...


class FlowApp(App):
	TITLE = "flow"
	CSS_PATH = "styles.tcss"
	COMMANDS: ClassVar = {FlowCommandProvider}
	COMMAND_PALETTE_BINDING: ClassVar[str] = "ctrl+p"
	BINDINGS: ClassVar = [
		Binding("ctrl+c", "interrupt", "abort/quit", priority=True),
		Binding("ctrl+d", "quit_app", "quit", priority=True),
		Binding("escape", "abort", "abort", show=False),
		Binding("ctrl+t", "toggle_thinking", "thinking", priority=True),
		Binding("ctrl+o", "toggle_tools", "tool output", priority=True),
	]

	def __init__(
		self,
		controller: ControllerLike,
		fatal_check: Callable[[], str | None] | None = None,
	):
		super().__init__()
		self.controller = controller
		# returns a fatal notice when the daemon this TUI owns has died; None = healthy
		# (or nobody to watch — `flow attach` has no child process)
		self.fatal_check = fatal_check

	def action_command_palette(self) -> None:
		if self.use_command_palette and not CommandPalette.is_open(self):
			self.push_screen(CommandPalette(id="--command-palette", placeholder="filter commands"))

	def compose(self) -> ComposeResult:
		yield ConversationView(id="conversation")
		yield Static(id="error-banner")
		yield WorkingStatus()
		yield Composer(id="composer")
		yield StatusBar(id="status")

	def on_mount(self) -> None:
		self.register_theme(flow_theme)
		self.theme = flow_theme.name
		if self._driver is not None:
			# Terminals title the window from the foreground process name, which is the
			# python interpreter behind the `flow` console script; set it explicitly.
			self._driver.write("\x1b]0;flow\x07")
		self.controller.on_changes = self.apply_changes
		self.controller.on_error = self._notify_controller_error
		self.query_one(Composer).focus()
		if self.fatal_check is not None:
			self.set_interval(1.0, self._check_daemon)
		self.run_worker(self._run_controller(), exclusive=True)

	def _check_daemon(self) -> None:
		"""Daemon crash is fatal by design: no auto-respawn — sessions are durable,
		rerunning `flow` recovers. Exit and surface the notice with the log path."""
		notice = self.fatal_check() if self.fatal_check is not None else None
		if notice is not None:
			self.exit(return_code=1, message=notice)

	async def _run_controller(self) -> None:
		try:
			await self.controller.connect()
			load_history = getattr(self.controller, "prompt_history", None)
			if load_history is not None:
				try:
					self.query_one(Composer).set_history(await load_history())
				except FlowAPIError as error:
					self.notify(f"could not load prompt history: {error.detail}", severity="warning")
			await self.controller.stream_events()
		except FlowAPIError as error:
			self.query_one("#error-banner", Static).update(f"✗ {error}")
			self.query_one("#error-banner").add_class("visible")
		finally:
			await self.controller.stop()

	def apply_changes(self, changes: list[Change]) -> None:
		conversation = self.query_one(ConversationView)
		state = self.controller.state
		for change in changes:
			if isinstance(change, EntryAdded):
				steered = change.entry.seq in self.controller.steered_seqs
				conversation.add_entry(change.entry, steered=steered)
			elif isinstance(change, EntryReplaced):
				conversation.replace_partial(change.entry)
			elif isinstance(change, StreamDelta):
				conversation.show_partial(state.partial)
			elif isinstance(change, PartialCleared):
				conversation.clear_partial()
			elif isinstance(change, EntriesTruncated):
				conversation.truncate(change.target_seq)
			elif isinstance(change, ApprovalChanged):
				pass  # phase 12: approval cards
			elif isinstance(change, StatusChanged):
				self._refresh_status()

	def _refresh_status(self) -> None:
		state = self.controller.state
		self.query_one(StatusBar).refresh_from(state, queued=len(self.controller.queued))
		self.query_one(WorkingStatus).set_running(state.running)
		self.query_one(ConversationView).set_running(state.running)
		banner = self.query_one("#error-banner", Static)
		if state.last_error is not None:
			banner.update(f"✗ {state.last_error.message}")
			banner.add_class("visible")
		else:
			banner.remove_class("visible")

	def on_composer_command_submitted(self, message: Composer.CommandSubmitted) -> None:
		self.run_worker(dispatch(self, message.line), exclusive=False)

	def prefill_composer(self, text: str) -> None:
		composer = self.query_one(Composer)
		composer.load_text(text)
		composer.move_cursor(composer.document.end)
		composer.focus()

	def on_composer_submitted(self, message: Composer.Submitted) -> None:
		if message.queue and self.controller.state.running:
			self.controller.queue(message.text)
			return
		self.run_worker(self._submit(message.text), exclusive=False)

	async def _submit(self, text: str) -> None:
		try:
			status = await self.controller.submit(text)
		except FlowAPIError as error:
			self.notify(str(error.detail), severity="error")
			return
		if status == "steered":
			self.notify("steering the active run", severity="information")

	def _notify_controller_error(self, error: FlowAPIError) -> None:
		self.notify(str(error.detail), severity="error", markup=False)

	def on_composer_edit_requested(self, message: Composer.EditRequested) -> None:
		self.action_edit_in_editor()

	def action_edit_in_editor(self) -> None:
		editor = resolve_editor()
		if editor is None:
			self.notify("set $VISUAL or $EDITOR to edit the draft externally", severity="warning")
			return
		composer = self.query_one(Composer)
		try:
			edited = edit_text_via_editor(composer.text, editor, self.suspend)
		except SuspendNotSupported:
			self.notify("external editing needs a real terminal", severity="error")
			return
		self.prefill_composer(edited.rstrip("\n"))

	def action_toggle_thinking(self) -> None:
		conversation = self.query_one(ConversationView)
		conversation.set_show_thinking(not conversation.show_thinking)

	def action_toggle_tools(self) -> None:
		conversation = self.query_one(ConversationView)
		conversation.set_expand_tools(not conversation.expand_tools)

	def action_interrupt(self) -> None:
		"""Ctrl+c aborts the run; ctrl+c while idle quits."""
		if self.controller.state.running:
			self.action_abort()
		else:
			self.exit()

	def action_quit_app(self) -> None:
		"""Ctrl+d quits like shell EOF, run or no run; teardown aborts and drains."""
		self.exit()

	def action_abort(self) -> None:
		"""Escape aborts the run and does nothing while idle — it never quits."""
		if self.controller.state.running:
			self.run_worker(self.controller.abort(), exclusive=False)
			self.notify("aborting…", severity="warning")


def run_app(
	url: str | None = None,
	*,
	uds: str | None = None,
	token: str | None = None,
	model: str = "mock",
	session_id: str | None = None,
	append_system_prompt: str | None = None,
	fatal_check: Callable[[], str | None] | None = None,
) -> str | None:
	"""Run the TUI against the daemon at `url`, or over the unix socket at `uds`;
	returns the last active session id.

	With `session_id` the TUI attaches to that session and replays its history
	(`flow tui -c`, `flow attach --session`); otherwise it creates a fresh one. The
	server composes the system prompt (preamble + AGENTS.md); the TUI only adds its
	client suffix and the user's `append_system_prompt`, which lands at the very end.
	`auto_approve=True` is the permanent default for TUI sessions;
	a `--confirm` flag lands with the approvals UI (phase 12).
	"""
	if (url is None) == (uds is None):
		raise ValueError("run_app needs exactly one of url or uds")
	config = SessionConfig(
		model=model,
		cwd=os.getcwd(),
		auto_approve=True,
		system_suffix=TUI_SYSTEM_SUFFIX,
		system_append=append_system_prompt,
	)
	client = FlowClient(url or UDS_URL, token=token, uds=uds)
	controller = Controller(client, session_id=session_id, config=config)
	FlowApp(controller, fatal_check=fatal_check).run()
	return controller.session_id
