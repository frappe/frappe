"""FlowApp — the TUI shell: transcript, composer, status bar.

The app is a view over the controller: it routes `Change` notices from the reducer to
widgets and user input back to controller verbs. `run_app()` is the entry point used
by bare `flow` and `flow attach`.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import ClassVar, Protocol

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Static

from flow.events import ReasoningEffort
from flow.session.config import SessionConfig
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
from flow_tui.widgets.composer import Composer
from flow_tui.widgets.conversation import ConversationView
from flow_tui.widgets.status_bar import StatusBar

TUI_SYSTEM_SUFFIX = (
	"## Client\n"
	"The user talks to you through the flow terminal UI. Keep answers terminal-friendly: "
	"plain text and fenced code blocks; no HTML."
)


class ControllerLike(Protocol):
	"""What the app needs from a controller — a seam so pilot tests can fake it."""

	state: ConversationState
	queued: list[str]
	steered_seqs: set[int]
	session_id: str | None
	on_changes: Callable[[list[Change]], None]

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
	async def list_models(self) -> list[dict]: ...
	async def new_session(self) -> str: ...
	async def switch_session(self, sid: str) -> None: ...


class FlowApp(App):
	TITLE = "flow"
	CSS_PATH = "styles.tcss"
	COMMANDS: ClassVar = {FlowCommandProvider}
	COMMAND_PALETTE_BINDING: ClassVar[str] = "ctrl+p"
	BINDINGS: ClassVar = [
		Binding("ctrl+c", "interrupt", "abort/quit", priority=True),
		Binding("escape", "interrupt", "abort", show=False),
		Binding("ctrl+t", "toggle_thinking", "thinking", priority=True),
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

	def compose(self) -> ComposeResult:
		yield ConversationView(id="conversation")
		yield Static(id="error-banner")
		yield Composer(id="composer")
		yield StatusBar(id="status")

	def on_mount(self) -> None:
		self.controller.on_changes = self.apply_changes
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
		self.query_one(StatusBar).refresh_from(
			state, session_id=self.controller.session_id, queued=len(self.controller.queued)
		)
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

	def action_toggle_thinking(self) -> None:
		conversation = self.query_one(ConversationView)
		conversation.set_show_thinking(not conversation.show_thinking)

	def action_interrupt(self) -> None:
		"""First ctrl+c/escape aborts the run; ctrl+c while idle quits."""
		if self.controller.state.running:
			self.run_worker(self.controller.abort(), exclusive=False)
			self.notify("aborting…", severity="warning")
		else:
			self.exit()


def run_app(
	url: str,
	*,
	token: str | None = None,
	model: str = "mock",
	session_id: str | None = None,
	fatal_check: Callable[[], str | None] | None = None,
) -> str | None:
	"""Run the TUI against the daemon at `url`; returns the last active session id.

	With `session_id` the TUI attaches to that session and replays its history
	(`flow -c`, `flow attach --session`); otherwise it creates a fresh one. The
	server composes the system prompt (preamble + AGENTS.md); the TUI only adds its
	client suffix. `auto_approve=True` is the permanent default for TUI sessions;
	a `--confirm` flag lands with the approvals UI (phase 12).
	"""
	config = SessionConfig(
		model=model,
		cwd=os.getcwd(),
		auto_approve=True,
		system_suffix=TUI_SYSTEM_SUFFIX,
	)
	client = FlowClient(url, token=token)
	controller = Controller(client, session_id=session_id, config=config)
	FlowApp(controller, fatal_check=fatal_check).run()
	return controller.session_id
