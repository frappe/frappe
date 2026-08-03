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

from flow.events import RunEnded, RunStarted, UserMessage
from flow.session.config import SessionConfig
from flow_tui.client.api import FlowClient
from flow_tui.client.state import Change, ConversationState, StatusChanged
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
		self.on_changes: Callable[[list[Change]], None] = lambda changes: None
		# seqs of user messages that steered an active run (any user message after the
		# run's initiating one, while the run is live) — the view marks them
		self.steered_seqs: set[int] = set()
		self._initiator_seen = False
		self._stream: EventStream | None = None

	async def connect(self) -> None:
		"""Create the session (unless attaching to one) and seed the state baseline."""
		if self.session_id is None:
			self.session_id = await self.client.create_session(self.config or SessionConfig())
		self.state.seed(await self.client.get_session(self.session_id))
		self.on_changes([StatusChanged()])

	async def stream_events(self) -> None:
		"""Fold the event stream into state until `stop()`; replay and live are one path."""
		assert self.session_id is not None, "connect() first"
		self._stream = EventStream(self.client, self.session_id)
		async for event in self._stream:
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

	async def stop(self) -> None:
		if self._stream is not None:
			await self._stream.stop()
		await self.client.aclose()

	async def _flush_queue(self) -> None:
		if not self.queued:
			return
		text = self.queued.pop(0)
		self.on_changes([StatusChanged()])
		await self.submit(text)
