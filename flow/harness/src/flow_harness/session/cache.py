# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Live `Session` objects, kept under one byte budget shared by every site.

Dropping a session loses nothing: its log has everything, and the store rebuilds it
on the next `get`. Over budget, the least recently used sessions go first; a session
with a run, a stream or a title in flight stays.

Evicting only drops the cache's reference. If something still holds the object, the
weak registry hands back that same object, because two objects over one log would
number their events twice.
"""

from __future__ import annotations

import os
import weakref
from collections import OrderedDict
from dataclasses import dataclass
from itertools import count
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from flow_harness.session.session import Session

# Measured: an empty session costs ~80 KB (object, tools, skills, system prompt), and
# its replayed transcript ~1.12x the log's bytes. Charged a little over, so the cap
# is a ceiling.
SESSION_OVERHEAD = 80 * 1024
TRANSCRIPT_FACTOR = 1.15

_Key = tuple[int, str]


class SessionCache:
	"""Least-recently-used, capped in bytes. Shared by every store in the process."""

	def __init__(self, max_bytes: int):
		self.max_bytes = max_bytes
		self.used_bytes = 0
		self._entries: OrderedDict[_Key, _Entry] = OrderedDict()  # oldest use first
		self._live: weakref.WeakValueDictionary[_Key, Session] = weakref.WeakValueDictionary()
		self._partitions = count()

	def partition(self) -> CachePartition:
		"""One store's window on the cache. Each store gets its own, so a store rebuilt
		on a tightened fence starts cold and revalidates what it loads."""
		return CachePartition(self, next(self._partitions))

	def put(self, key: _Key, session: Session) -> None:
		self._forget(key)
		self._entries[key] = entry = _Entry(session, _cost(session))
		self._live[key] = session
		self.used_bytes += entry.cost
		self._evict()

	def get(self, key: _Key) -> Session | None:
		"""Hand the session to a caller as its newest use. An evicted session that
		someone still holds comes back from the weak registry."""
		entry = self._entries.get(key)
		if entry is None:
			session = self._live.get(key)
			if session is not None:
				self.put(key, session)
			return session
		self._entries.move_to_end(key)
		return entry.session

	def peek(self, key: _Key) -> Session | None:
		"""Read live values off a session without counting as a use, so listing every
		session cannot promote them all."""
		entry = self._entries.get(key)
		return entry.session if entry is not None else self._live.get(key)

	def settled(self, key: _Key) -> None:
		"""A run, a title or the last stream on this session ended: charge what it holds
		now, then evict. Not a use, so its place in the order stays."""
		entry = self._entries.get(key)
		if entry is not None:
			self.used_bytes += (cost := _cost(entry.session)) - entry.cost
			entry.cost = cost
		self._evict()

	def drop(self, key: _Key) -> None:
		self._forget(key)
		self._live.pop(key, None)

	def sessions(self, partition: int) -> list[Session]:
		"""Every live session of one store, cached or merely still referenced."""
		found = {key: session for key, session in self._live.items() if key[0] == partition}
		found.update({key: entry.session for key, entry in self._entries.items() if key[0] == partition})
		return list(found.values())

	def __contains__(self, key: _Key) -> bool:
		"""Cached, meaning it is holding budget — not merely still referenced."""
		return key in self._entries

	def _evict(self) -> None:
		"""Drop least-recently-used sessions until inside the budget, skipping any a run,
		a stream, or a title still needs. Dropping one frees nothing durable."""
		if self.used_bytes <= self.max_bytes:
			return
		for key, entry in list(self._entries.items()):
			if self.used_bytes <= self.max_bytes:
				return
			if not entry.session.in_use:
				self._forget(key)

	def _forget(self, key: _Key) -> None:
		entry = self._entries.pop(key, None)
		if entry is not None:
			self.used_bytes -= entry.cost


class CachePartition:
	"""One store's sessions inside the shared cache, keyed by session id."""

	def __init__(self, cache: SessionCache, partition: int):
		self.cache = cache
		self._partition = partition

	def put(self, session: Session) -> None:
		self.cache.put((self._partition, session.id), session)

	def get(self, sid: str) -> Session | None:
		return self.cache.get((self._partition, sid))

	def peek(self, sid: str) -> Session | None:
		return self.cache.peek((self._partition, sid))

	def settled(self, session: Session) -> None:
		self.cache.settled((self._partition, session.id))

	def drop(self, sid: str) -> None:
		self.cache.drop((self._partition, sid))

	def sessions(self) -> list[Session]:
		return self.cache.sessions(self._partition)

	def __contains__(self, sid: str) -> bool:
		return (self._partition, sid) in self.cache


@dataclass
class _Entry:
	session: Session
	cost: int


def _cost(session: Session) -> int:
	"""What holding this session costs: the object, plus the transcript replayed from
	its log. A log that cannot be stat'ed is charged the fixed part alone."""
	try:
		return SESSION_OVERHEAD + int(os.path.getsize(session.log.path) * TRANSCRIPT_FACTOR)
	except OSError:
		return SESSION_OVERHEAD
