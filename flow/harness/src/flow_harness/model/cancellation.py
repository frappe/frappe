"""Cancellation-aware awaiting for streamed provider work.

`ModelCancelled` is the internal control flow these helpers raise the moment a
request's cancellation signal is set; callers turn it into a graceful terminal.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable
from contextlib import suppress
from typing import Any


class ModelCancelled(Exception):
	"""Internal control flow raised when a request's cancellation signal is set."""


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
