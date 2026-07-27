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
					last = _entry_seq(json.loads(line))
		return last

	def append(self, event: _Event) -> int:
		"""Assign the next seq, persist the event, return the seq."""
		self._seq += 1
		event.seq = self._seq
		os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
		fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
		os.chmod(self.path, 0o600)
		with os.fdopen(fd, "a", encoding="utf-8") as f:
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
				if _entry_seq(entry) > since:
					out.append(entry)
		return out

	@property
	def latest_seq(self) -> int:
		return self._seq


def _entry_seq(entry: dict) -> int:
	seq = entry.get("seq")
	if type(seq) is not int:
		raise ValueError("persisted log entry is missing a valid integer seq")
	return seq
