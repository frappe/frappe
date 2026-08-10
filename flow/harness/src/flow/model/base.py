"""The provider contract: one `Model.run` call is one streamed model turn.

An adapter yields `TextDelta` / `ThinkingDelta` / `ToolCallStarted` while streaming and
always terminates with an `AssistantMessage` followed by a `Usage`. Everything that can
go wrong with a provider is owned here too, so the agent loop never has to care:

  - failures are raised as a typed `ProviderError` (see `errors.py`);
  - transient failures are retried inside the stream by `run_with_retries`, which
    emits `Retry` progress events between attempts — a retry may only happen before the terminal
    `AssistantMessage` is out, since that is the moment the turn becomes durable;
  - cancellation ends the turn gracefully with an `AssistantMessage(stop_reason=
    "aborted")`, so an aborted run still leaves a well-formed transcript.
"""

from __future__ import annotations

import abc
import asyncio
import random
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from flow.events import AnyEvent, AssistantMessage, Retry, TranscriptMessage
from flow.model.errors import ProviderError, credential_refresh_error

_RETRY_BASE_DELAY_SECONDS = 0.5
_RETRY_MAX_BACKOFF_SECONDS = 8.0
# A provider hint asking us to wait longer than this means the call is not worth
# retrying at all.
_RETRY_MAX_PROVIDER_DELAY_SECONDS = 60.0
_MAX_TRANSIENT_RETRIES = 2


@dataclass(slots=True)
class ModelRequest:
	"""Provider-neutral input for one model turn.

	``cancellation`` is owned by the session. Adapters race their transport against it
	so a hung provider cannot hold a run open.
	"""

	messages: list[TranscriptMessage]
	tools: list[dict[str, Any]] | None = None
	system_prompt: str = "You are a helpful assistant."
	stream: bool = True
	cancellation: asyncio.Event | None = None
	max_output_tokens: int | None = None
	resolve_attachment: Callable[[str], bytes] | None = None


class ModelCancelled(Exception):
	"""Internal control flow raised when a request's cancellation signal is set."""


class Model(abc.ABC):
	name: str
	api: str = "unknown"
	provider: str = "unknown"
	model: str = "unknown"

	@property
	def supports_images(self) -> bool:
		"""Whether this exact serving surface accepts image input."""
		return False

	@property
	def context_window(self) -> int | None:
		"""Tokens of context the model accepts; None means unknown."""
		return None

	@property
	def max_output_tokens(self) -> int | None:
		"""Largest output the model accepts; None means the adapter does not know."""
		return None

	@property
	def auto_compact_threshold_tokens(self) -> int | None:
		"""Provider-recommended input size for automatic compaction, if known."""
		return None

	async def load_model_limits(self, cancellation: asyncio.Event | None = None) -> None:
		"""Load serving-surface-specific limits when a provider exposes them."""
		return None

	@abc.abstractmethod
	def run(self, request: ModelRequest) -> AsyncIterator[AnyEvent]:
		"""Run one model turn over the provider-neutral transcript, yielding typed events."""

	def aborted_message(self) -> AssistantMessage:
		"""The graceful terminal for a cancelled turn."""
		return AssistantMessage(api=self.api, provider=self.provider, model=self.model, stop_reason="aborted")


# --- cancellation ----------------------------------------------------------


async def await_with_cancellation(awaitable: Awaitable[Any], cancellation: asyncio.Event | None) -> Any:
	"""Await one provider operation while making cancellation win any completion race."""
	if cancellation is None:
		return await awaitable

	task = asyncio.ensure_future(awaitable)
	if cancellation.is_set():
		task.cancel()
		with suppress(asyncio.CancelledError):
			await task
		raise ModelCancelled
	cancel_wait = asyncio.create_task(cancellation.wait())
	try:
		done, _ = await asyncio.wait({task, cancel_wait}, return_when=asyncio.FIRST_COMPLETED)
		if cancel_wait in done:
			task.cancel()
			with suppress(asyncio.CancelledError):
				await task
			raise ModelCancelled
		return await task
	except asyncio.CancelledError:
		task.cancel()
		with suppress(asyncio.CancelledError):
			await task
		raise
	finally:
		cancel_wait.cancel()
		with suppress(asyncio.CancelledError):
			await cancel_wait


async def iterate_with_cancellation(
	iterator: AsyncIterator[Any], cancellation: asyncio.Event | None
) -> AsyncIterator[Any]:
	"""Consume and close an async iterator, stopping the moment cancellation is requested."""
	try:
		while True:
			try:
				item = await await_with_cancellation(anext(iterator), cancellation)
			except StopAsyncIteration:
				return
			yield item
	finally:
		await aclose(iterator)


async def aclose(iterator: AsyncIterator[Any]) -> None:
	"""Release an iterator we are done with.

	`async for` does not close what it iterates, so an abandoned provider stream would
	otherwise stay suspended — holding its connection — until the event loop shuts down.
	"""
	close = getattr(iterator, "aclose", None)
	if close is not None:
		with suppress(Exception):
			await close()


# --- the shared retry envelope --------------------------------------------


async def run_with_retries(
	start_attempt: Callable[[], AsyncIterator[AnyEvent]],
	*,
	cancellation: asyncio.Event | None = None,
	refresh_auth: Callable[[], Awaitable[None]] | None = None,
	provider: str = "unknown",
) -> AsyncIterator[AnyEvent]:
	"""Run one model turn with bounded retries, emitting `Retry` progress in-stream.

	``start_attempt`` begins one fresh provider attempt. An attempt may be retried
	only while nothing durable is out: once it has yielded its `AssistantMessage`, a
	failure propagates instead. A failed attempt's live deltas have already escaped —
	`Retry(status="started")` is the boundary at which a client discards them.

	``refresh_auth`` is the one-shot auth recovery: on a retryable auth failure it is awaited
	once (re-resolving credentials in place) and the turn is attempted again. Transient
	failures never consume the refresh slot, and auth failures never consume the
	transient budget.
	"""
	attempt = 1
	max_attempts = 1 + _MAX_TRANSIENT_RETRIES + (1 if refresh_auth is not None else 0)
	transient_used = 0
	refresh_used = False

	while True:
		committed = False
		attempt_events = start_attempt()
		try:
			async for event in attempt_events:
				committed = committed or isinstance(event, AssistantMessage)
				yield event
			return
		except ProviderError as error:
			if committed:
				raise
			delay = _retry_delay_seconds(error, transient_used)
			can_refresh = (
				error.kind == "auth" and error.retryable and refresh_auth is not None and not refresh_used
			)
			can_retry = (
				error.retryable
				and error.kind != "auth"
				and transient_used < _MAX_TRANSIENT_RETRIES
				and delay <= _RETRY_MAX_PROVIDER_DELAY_SECONDS
			)
			if not can_refresh and not can_retry:
				if attempt > 1:  # close a retry lifecycle this turn actually opened
					yield Retry(status="exhausted", attempt=attempt, kind=error.kind)
				raise

			next_attempt = attempt + 1
			if can_refresh:
				delay = 0.0
			yield Retry(
				status="scheduled",
				attempt=next_attempt,
				max_attempts=max_attempts,
				delay_seconds=delay,
				kind=error.kind,
			)
			await await_with_cancellation(asyncio.sleep(delay), cancellation)
			if can_refresh:
				assert refresh_auth is not None
				try:
					await await_with_cancellation(refresh_auth(), cancellation)
				except (ModelCancelled, ProviderError) as refresh_error:
					if isinstance(refresh_error, ProviderError):
						yield Retry(status="exhausted", attempt=attempt, kind=refresh_error.kind)
					raise
				except Exception as exc:
					# The token endpoint is a second provider call; its faults must
					# not escape untyped.
					refreshed_error = credential_refresh_error(exc, provider=error.provider or provider)
					yield Retry(status="exhausted", attempt=attempt, kind=refreshed_error.kind)
					raise refreshed_error from exc
				refresh_used = True
			else:
				transient_used += 1
			yield Retry(status="started", attempt=next_attempt)
			attempt = next_attempt
		finally:
			await aclose(attempt_events)


def _retry_delay_seconds(error: ProviderError, retry_index: int) -> float:
	"""Honour the provider's own retry hint, else jittered exponential backoff."""
	if error.retry_after_seconds is not None:
		return error.retry_after_seconds
	base = min(_RETRY_BASE_DELAY_SECONDS * (2**retry_index), _RETRY_MAX_BACKOFF_SECONDS)
	return random.uniform(base * 0.75, base)
