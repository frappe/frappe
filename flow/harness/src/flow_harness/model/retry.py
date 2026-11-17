"""The shared retry envelope around one streamed model turn."""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator, Awaitable, Callable

from flow_harness.events import AnyEvent, AssistantMessage, Retry
from flow_harness.model.cancellation import ModelCancelled, aclose, await_with_cancellation
from flow_harness.model.errors import ProviderError, credential_refresh_error

_RETRY_BASE_DELAY_SECONDS = 0.5
_RETRY_MAX_BACKOFF_SECONDS = 8.0
# A provider hint asking us to wait longer than this means the call is not worth
# retrying at all.
_RETRY_MAX_PROVIDER_DELAY_SECONDS = 60.0
_MAX_TRANSIENT_RETRIES = 2


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
