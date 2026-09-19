"""A simple in-process front door over the durable session.

One `Agent` object whose `run()`/`resume()` yield the live event stream — the ergonomic
path for embedding, tests, and scripts. The daemon and remote clients use the Session
verbs + `Session.events` directly; this is a thin wrapper over the same engine
(subscribe -> submit the run -> yield events until the run ends)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from typing import Any

from flow_harness import config as server_config
from flow_harness.events import AnyEvent
from flow_harness.model import Model
from flow_harness.session.config import SessionConfig
from flow_harness.session.session import RunHandle, Session
from flow_harness.session.store import SessionStore


class Agent:
	def __init__(
		self,
		config: SessionConfig | None = None,
		*,
		data_dir: str = server_config.DATA_DIR,
		**overrides: Any,
	):
		# Extension paths configure executable server resources, not durable session data.
		extension_paths = overrides.pop("extension_paths", None)
		extensions_enabled = overrides.pop("extensions_enabled", False)
		# `model=` may be a name string (goes to config, resolved via get_model) or a
		# pre-built Model instance (injected directly — used by tests and embedders).
		injected = overrides.pop("model", None)
		if isinstance(injected, Model):
			self._model: Model | None = injected
		else:
			self._model = None
			if injected is not None:
				overrides["model"] = injected
		self._session = SessionStore(
			data_dir,
			extension_paths=extension_paths,
			extensions_enabled=extensions_enabled,
		).create(config or SessionConfig(**overrides))

	@property
	def session(self) -> Session:
		return self._session

	def run(self, message: str, **hooks: Any) -> AsyncIterator[AnyEvent]:
		"""Start a turn; yields the live event stream until the run ends or pauses."""
		return self._events(lambda: self._session.run(message, model=self._model, **hooks))

	def resume(
		self,
		answers: dict[str, str],
		*,
		approval_seq: int | None = None,
		**hooks: Any,
	) -> AsyncIterator[AnyEvent]:
		"""Continue a paused run; yields the event stream of the continuation. A batch a
		running sub-agent waits on is answered too, and yields nothing: its continuation
		stays in the run's own stream."""
		return self._events(
			lambda: self._session.resume(answers, approval_seq=approval_seq, model=self._model, **hooks)
		)

	def compact(self, instructions: str | None = None) -> AsyncIterator[AnyEvent]:
		"""Summarize the conversation into a durable compaction entry; yields until done."""
		return self._events(lambda: self._session.compact(instructions, model=self._model))

	def abort(self) -> bool:
		"""Signal the active run to stop; return whether a run was active."""
		return self._session.abort()

	async def rewind(self, target_seq: int) -> None:
		"""Move the conversation back to an earlier entry; the next run branches from it."""
		await self._session.rewind(target_seq)

	async def set_model(self, model: str, credential_id: str | None = None) -> None:
		"""Select the model (and credential) for later runs; durable and per-branch."""
		if self._model is not None:
			raise RuntimeError("runs use the injected Model instance; set_model cannot switch it")
		await self._session.set_model(model, credential_id=credential_id)

	async def _events(self, submit: Callable[[], Awaitable[RunHandle]]) -> AsyncIterator[AnyEvent]:
		queue = self._session.subscribe()  # subscribe before the run starts so no event is missed
		task: asyncio.Task[None] | None = None
		next_event: asyncio.Task[AnyEvent | None] | None = None
		try:
			handle = await submit()
			if handle.status == "resumed":  # the answers reached a child inside the run being streamed
				return
			if handle.status != "started":
				raise RuntimeError("session already has an active run")
			task = handle.task
			assert task is not None
			while True:
				if task.done() and queue.empty():
					await task  # surfaces a run that died without its terminal event
					return
				next_event = asyncio.create_task(queue.get())
				done, _ = await asyncio.wait((next_event, task), return_when=asyncio.FIRST_COMPLETED)
				if next_event not in done:
					next_event.cancel()
					with suppress(asyncio.CancelledError):
						await next_event
					continue
				event = next_event.result()
				if event is None:
					raise RuntimeError("event subscriber fell behind")
				yield event
				if event.type == "run_ended" and event.subagent_id is None:  # the run's own terminal event
					break
		finally:
			if next_event is not None and not next_event.done():
				next_event.cancel()
				with suppress(asyncio.CancelledError):
					await next_event
			self._session.unsubscribe(queue)
			if task is not None:
				await task
