"""Serve a session's event feed as Server-Sent Events."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator

from flow_harness.session.session import Session

# follow-mode keepalive cadence; a module global so tests can shrink it
KEEPALIVE_SECONDS = 15.0


async def sse_follow_stream(session: Session, since: int, closing: asyncio.Event) -> AsyncIterator[bytes]:
	"""Follow mode: never close at a run boundary. The subscription stays attached
	between runs and an SSE comment goes out whenever the feed is quiet, so proxies
	and dead-peer detection keep working while the session idles."""
	since = min(since, session.log.latest_seq)
	events = session.events(since)
	pending = asyncio.ensure_future(anext(events))
	closed = asyncio.ensure_future(closing.wait())
	try:
		while True:
			done, _ = await asyncio.wait(
				{pending, closed}, timeout=KEEPALIVE_SECONDS, return_when=asyncio.FIRST_COMPLETED
			)
			if closed in done:
				return  # the daemon is shutting down; an open stream would hold it up
			if not done:
				yield b": keepalive\n\n"
				continue
			try:
				event = pending.result()
			except StopAsyncIteration:
				return
			yield _sse(event.model_dump(exclude_none=True))
			pending = asyncio.ensure_future(anext(events))
	finally:
		closed.cancel()
		pending.cancel()
		with contextlib.suppress(asyncio.CancelledError):
			await pending
		await events.aclose()


async def sse_stream(session: Session, since: int) -> AsyncIterator[bytes]:
	"""Serve `session.events` as SSE, closing where a reconnecting client expects: when
	the watched run ends, or once a session with no active run is fully replayed."""
	since = min(since, session.log.latest_seq)  # a future cursor would suppress live events
	boundary = session.log.latest_seq  # replay ends here: no await before events() attaches
	if not session.is_running and boundary <= since:
		return
	async for event in session.events(since):
		yield _sse(event.model_dump(exclude_none=True))
		if event.type == "run_ended" and event.seq is not None and event.seq >= boundary:
			return  # the live run (or the final historical one) is over
		if event.seq == boundary and not session.is_running:
			return  # replay is done and no live run follows


def _sse(data: dict) -> bytes:
	return f"data: {json.dumps(data)}\n\n".encode()
