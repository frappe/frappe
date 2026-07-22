"""Append-only, sequence-numbered event log — the durable source of truth for a run.

Every durable event gets a monotonic `seq`. `read_since(n)` is both the replay path
(catch a reconnecting client up) and the restart path (rebuild state from disk). This
is what lets a run survive a dropped connection or a daemon restart.
"""

from __future__ import annotations

import json
import os

from flow_server.events import _Event


class SessionLog:
	def __init__(self, path: str):
		self.path = path
		self._seq = self._scan_max_seq()

	def _scan_max_seq(self) -> int:
		if not os.path.isfile(self.path):
			return 0
		last = 0
		with open(self.path, encoding="utf-8") as f:
			for line in f:
				line = line.strip()
				if line:
					last = json.loads(line).get("seq", last)
		return last

	def append(self, event: _Event) -> int:
		"""Assign the next seq, persist the event, return the seq."""
		self._seq += 1
		event.seq = self._seq
		os.makedirs(os.path.dirname(self.path), exist_ok=True)
		with open(self.path, "a", encoding="utf-8") as f:
			f.write(event.model_dump_json() + "\n")
			f.flush()
			os.fsync(f.fileno())
		return self._seq

	def read_since(self, since: int) -> list[dict]:
		if not os.path.isfile(self.path):
			return []
		out: list[dict] = []
		with open(self.path, encoding="utf-8") as f:
			for line in f:
				line = line.strip()
				if not line:
					continue
				entry = json.loads(line)
				if entry.get("seq", 0) > since:
					out.append(entry)
		return out

	@property
	def latest_seq(self) -> int:
		return self._seq
