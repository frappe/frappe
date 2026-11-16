"""Reconnecting event stream over the daemon's SSE endpoint.

`EventStream` opens `/stream?since=<cursor>&follow=true` and yields typed events. The
cursor advances only on durable events, and anything at or below it is dropped, so a
reconnect race can never double-render an entry. Transport errors and unexpected closes
reconnect with backoff from the cursor; HTTP error statuses raise — they mean the
request itself is wrong (bad session, bad token), and a retry cannot fix that.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import httpx

from flow_harness.events import AnyEvent, parse_event
from flow_tui.client.api import FlowAPIError, FlowClient


async def parse_sse(lines: AsyncIterator[str]) -> AsyncIterator[str]:
	"""Yield the data payload of each SSE message; comment lines (keepalives) vanish."""
	data: list[str] = []
	async for line in lines:
		if not line:
			if data:
				yield "\n".join(data)
				data = []
		elif line.startswith(":"):
			continue
		elif line.startswith("data:"):
			data.append(line[5:].lstrip())


class EventStream:
	def __init__(
		self,
		client: FlowClient,
		session_id: str,
		*,
		since: int = 0,
		backoff_initial: float = 0.5,
		backoff_max: float = 10.0,
	):
		self.client = client
		self.session_id = session_id
		self.cursor = since
		self._backoff_initial = backoff_initial
		self._backoff_max = backoff_max
		self._stopped = False
		self._response: httpx.Response | None = None

	async def stop(self) -> None:
		"""Close the stream; a blocked iteration wakes up and returns cleanly."""
		self._stopped = True
		if self._response is not None:
			await self._response.aclose()

	def __aiter__(self) -> AsyncIterator[AnyEvent]:
		return self.events()

	async def events(self) -> AsyncIterator[AnyEvent]:
		backoff = self._backoff_initial
		while not self._stopped:
			try:
				async with self.client.sse(self.session_id, since=self.cursor) as response:
					if response.status_code >= 400:
						await response.aread()
						raise FlowAPIError(response.status_code, response.text)
					self._response = response
					async for payload in parse_sse(response.aiter_lines()):
						event = parse_event(json.loads(payload))
						backoff = self._backoff_initial
						if event.durable and event.seq is not None:
							if event.seq <= self.cursor:
								continue
							self.cursor = event.seq
						yield event
						if self._stopped:
							return
			except (httpx.TransportError, httpx.StreamError):
				pass  # dropped mid-flight; fall through to the reconnect path
			finally:
				self._response = None
			if self._stopped:
				return
			# in follow mode the server never closes on purpose, so a clean close is
			# as unexpected as a transport error: back off, reconnect from the cursor
			await asyncio.sleep(backoff)
			backoff = min(backoff * 2, self._backoff_max)
