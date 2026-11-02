"""Glue between the client core and the app.

The controller owns `FlowClient`, the reconnecting `EventStream`, and the
`ConversationState` reducer; the app registers one `on_changes` callback and renders
from the change notices — widgets never touch httpx, so the app is pilot-testable
with a fake controller.

The client-side message queue (alt+enter) lives here, not in the stream: it survives
reconnects and flushes one message per `run_ended`.
"""

from __future__ import annotations

from collections.abc import Callable

from flow_harness import settings
from flow_harness.events import ReasoningEffort, RunEnded, RunStarted, UserMessage
from flow_harness.session.config import SessionConfig
from flow_harness.session.skills import parse_skill_invocation
from flow_tui.client.api import FlowAPIError, FlowClient
from flow_tui.client.state import (
	Change,
	ConversationState,
	EntriesTruncated,
	PartialCleared,
	StatusChanged,
)
from flow_tui.client.stream import EventStream


class Controller:
	def __init__(
		self,
		client: FlowClient,
		*,
		session_id: str | None = None,
		config: SessionConfig | None = None,
	):
		self.client = client
		self.session_id = session_id
		self.config = config
		self.state = ConversationState()
		self.queued: list[str] = []
		self.skills: list[dict] = []
		self.on_changes: Callable[[list[Change]], None] = lambda changes: None
		self.on_error: Callable[[FlowAPIError], None] = lambda error: None
		# seqs of user messages that steered an active run (any user message after the
		# run's initiating one, while the run is live) — the view marks them
		self.steered_seqs: set[int] = set()
		self._initiator_seen = False
		self._stream: EventStream | None = None
		self._switch_pending = False

	async def connect(self) -> None:
		"""Create the session (unless attaching to one) and seed the state baseline."""
		if self.session_id is None:
			self.session_id = await self.client.create_session(self.config or SessionConfig())
		self.state.seed(await self.client.get_session(self.session_id))
		self.skills = await self._load_skills(self.session_id)
		self.on_changes([StatusChanged()])

	async def stream_events(self) -> None:
		"""Fold the event stream into state until `stop()`; replay and live are one path.

		A session switch stops the inner stream and the loop reopens one for the new
		session id, so the caller's single `stream_events()` task spans switches.
		"""
		assert self.session_id is not None, "connect() first"
		while True:
			sid = self.session_id
			self._stream = EventStream(self.client, sid)
			async for event in self._stream:
				if self.session_id != sid:
					break  # switched away mid-yield; this event belongs to the old session
				if isinstance(event, RunStarted):
					self._initiator_seen = False
				elif isinstance(event, UserMessage):
					if self.state.running and self._initiator_seen and event.seq is not None:
						self.steered_seqs.add(event.seq)
					self._initiator_seen = True
				changes = self.state.apply(event)
				if changes:
					self.on_changes(changes)
				if isinstance(event, RunEnded) and event.reason != "paused":
					await self._flush_queue()
			if not self._switch_pending:
				return
			self._switch_pending = False

	async def submit(self, text: str) -> str:
		"""Send a message; returns "started" for a fresh run, "steered" mid-run."""
		assert self.session_id is not None
		result = await self.client.run(self.session_id, text)
		return result.get("status", "started")

	def queue(self, text: str) -> None:
		self.queued.append(text)
		self.on_changes([StatusChanged()])

	async def abort(self) -> None:
		assert self.session_id is not None
		await self.client.abort(self.session_id)

	async def change_model(self, model: str) -> None:
		"""Switch the model, keeping the current effort; the server picks the credential.

		A successful switch is remembered: `/new` in this session and the next
		launch both start on it.
		"""
		assert self.session_id is not None
		await self.client.set_model(self.session_id, model, reasoning_effort=self.state.reasoning_effort)
		if self.config is not None:
			self.config.model = model
		settings.save_setting("last_model", model)

	async def change_effort(self, effort: ReasoningEffort | None) -> None:
		"""Change effort on the current model/credential; None = provider default."""
		assert self.session_id is not None and self.state.model is not None
		await self.client.set_model(
			self.session_id,
			self.state.model,
			credential_id=self.state.credential_id,
			reasoning_effort=effort,
		)

	async def rewind(self, target_seq: int) -> None:
		assert self.session_id is not None
		await self.client.rewind(self.session_id, target_seq)

	async def list_sessions(self) -> list[dict]:
		return await self.client.list_sessions()

	async def list_models(self) -> dict:
		return await self.client.list_models()

	async def reload_extensions(self) -> dict:
		return await self.client.reload_extensions()

	async def prompt_history(self, limit: int = 100) -> list[str]:
		"""Return recent prompts, oldest first, with the active session first in
		reverse navigation and then earlier sessions by recent activity."""
		if limit <= 0:
			return []
		sessions = await self.client.list_sessions()
		sids = [item["session_id"] for item in sessions]
		if self.session_id is not None:
			sids = [self.session_id, *(sid for sid in sids if sid != self.session_id)]

		recent: list[str] = []
		for sid in sids:
			data = await self.client.entries(sid, path="all")
			for entry in reversed(data["entries"]):
				if entry.get("type") == "user_message":
					content = entry.get("content", "")
					if isinstance(content, str):
						text = content
					else:
						text = "".join(
							block.get("text", "")
							for block in content
							if isinstance(block, dict) and block.get("type") == "text"
						)
					invocation = parse_skill_invocation(text)
					if invocation is not None:
						text = invocation.command
					if text:
						recent.append(text)
					if len(recent) == limit:
						return list(reversed(recent))
		return list(reversed(recent))

	async def new_session(self) -> str:
		"""Create a fresh session from the launch config and switch to it."""
		sid = await self.client.create_session(self.config or SessionConfig())
		await self.switch_session(sid)
		return sid

	async def switch_session(self, sid: str) -> None:
		"""Point the controller at another session on the same daemon.

		The old stream stops (`stream_events` reopens one for the new id), state and
		queue reset, and the view clears before the new session's history replays
		through the fresh stream from seq 0 — replay and live stay one code path.
		"""
		self._switch_pending = self._stream is not None
		if self._stream is not None:
			await self._stream.stop()
		self.session_id = sid
		self.state = ConversationState()
		self.queued.clear()
		self.steered_seqs.clear()
		self._initiator_seen = False
		self.on_changes([PartialCleared(), EntriesTruncated(target_seq=0), StatusChanged()])
		self.state.seed(await self.client.get_session(sid))
		self.skills = await self._load_skills(sid)
		self.on_changes([StatusChanged()])

	async def _load_skills(self, sid: str) -> list[dict]:
		load = getattr(self.client, "skills", None)
		if load is None:
			return []
		return (await load(sid)).get("skills", [])

	async def stop(self) -> None:
		if self._stream is not None:
			await self._stream.stop()
		await self.client.aclose()

	async def _flush_queue(self) -> None:
		while self.queued:
			text = self.queued.pop(0)
			self.on_changes([StatusChanged()])
			try:
				await self.submit(text)
			except FlowAPIError as error:
				self.on_error(error)
				continue
			return
