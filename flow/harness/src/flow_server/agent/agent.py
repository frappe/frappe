"""A simple in-process front door over the durable agent loop.

One `Agent` object whose `run()`/`resume()` yield the live event stream — the ergonomic
path for embedding, the TUI, tests, and scripts. The daemon and remote clients use the
loop's `run()`/`resume()` functions + the session event log directly; this is a thin
wrapper over the same engine (subscribe -> spawn the run -> yield events until it ends).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import suppress
from typing import Any

from flow_server import config as server_config
from flow_server.agent.loop import resume as _resume
from flow_server.agent.loop import run as _run
from flow_server.events import _Event
from flow_server.model import Model
from flow_server.session.store import Session, SessionConfig, SessionState, SessionStore


class Agent:
	def __init__(
		self,
		config: SessionConfig | None = None,
		*,
		data_dir: str = server_config.DATA_DIR,
		**overrides: Any,
	):
		# `model=` may be a name string (goes to config, resolved via get_model) or a
		# pre-built Model instance (injected directly — used by tests and embedders).
		injected = overrides.pop("model", None)
		if isinstance(injected, Model):
			self._model: Model | None = injected
		else:
			self._model = None
			if injected is not None:
				overrides["model"] = injected
		self._session = SessionStore(data_dir).create(config or SessionConfig(**overrides))

	@property
	def session(self) -> Session:
		return self._session

	def run(self, message: str, **hooks: Any) -> AsyncIterator[_Event]:
		"""Start a turn; yields the live event stream until the run ends or pauses."""
		return self._drive(
			lambda: _run(self._session, message, model=self._model, **hooks),
			from_state=SessionState.IDLE,
		)

	def resume(
		self,
		answers: dict[str, str],
		*,
		approval_seq: int | None = None,
		**hooks: Any,
	) -> AsyncIterator[_Event]:
		"""Continue a paused run; yields the event stream of the continuation."""
		return self._drive(
			lambda: _resume(
				self._session,
				answers,
				approval_seq=approval_seq,
				model=self._model,
				**hooks,
			),
			from_state=SessionState.PAUSED,
		)

	async def _drive(
		self,
		make_coro: Callable[[], Coroutine[Any, Any, None]],
		*,
		from_state: SessionState,
	) -> AsyncIterator[_Event]:
		q = self._session.subscribe()  # subscribe before the run starts so no event is missed
		task: asyncio.Task[None] | None = None
		next_event: asyncio.Task[Any] | None = None
		try:
			async with self._session.operation_lock:
				if self._session.state is not from_state:
					raise RuntimeError(
						f"session must be {from_state} to start this operation "
						f"(current state: {self._session.state})"
					)
				task = self._session._start_operation(make_coro())
			while True:
				if task.done() and q.empty():
					await task
					return
				next_event = asyncio.create_task(q.get())
				done, _ = await asyncio.wait(
					(next_event, task),
					return_when=asyncio.FIRST_COMPLETED,
				)
				if next_event not in done:
					next_event.cancel()
					with suppress(asyncio.CancelledError):
						await next_event
					continue
				ev = next_event.result()
				yield ev
				if ev.type == "run_ended":  # always the terminal event
					break
		finally:
			if next_event is not None and not next_event.done():
				next_event.cancel()
				with suppress(asyncio.CancelledError):
					await next_event
			self._session.unsubscribe(q)
			if task is not None:
				await task
