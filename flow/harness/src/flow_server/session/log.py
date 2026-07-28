"""Append-only, sequence-numbered event log — the durable source of truth for a run.

Every durable event gets a monotonic `seq`. `read_since(n)` is both the replay path
(catch a reconnecting client up) and the restart path (rebuild state from disk). This
is what lets a run survive a dropped connection or a daemon restart.
"""

from __future__ import annotations

import json
import os
import threading

from pydantic import ValidationError

from flow_server.events import _Event, parse_event


class SessionLogError(ValueError):
	"""A persisted JSONL row violates the session-log contract."""


class SessionLog:
	def __init__(self, path: str):
		self.path = path
		self._lock = threading.Lock()
		self._seq = self._scan_max_seq()

	def _scan_max_seq(self) -> int:
		rows = _read_rows(self.path)
		return rows[-1]["seq"] if rows else 0

	def append(self, event: _Event) -> int:
		"""Assign the next seq, persist the event, return the seq."""
		with self._lock:
			if not event.durable:
				raise ValueError("live-only events cannot be appended to the session log")
			next_seq = self._seq + 1
			persisted = event.model_copy(update={"seq": next_seq})
			data = (persisted.model_dump_json(exclude_none=True) + "\n").encode()
			os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
			fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
			try:
				os.chmod(self.path, 0o600)
				if os.write(fd, data) != len(data):
					raise OSError("short write while appending session log")
				self._seq = next_seq
				event.seq = next_seq
				os.fsync(fd)
			finally:
				os.close(fd)
			return next_seq

	def read_since(self, since: int) -> list[dict]:
		with self._lock:
			return [row for row in _read_rows(self.path) if row["seq"] > since]

	@property
	def latest_seq(self) -> int:
		with self._lock:
			return self._seq


def _read_rows(path: str) -> list[dict]:
	if not os.path.isfile(path):
		return []
	rows: list[dict] = []
	previous_seq = 0
	with open(path, encoding="utf-8") as file:
		for line_number, line in enumerate(file, start=1):
			if not line.strip():
				continue
			try:
				entry = json.loads(line)
			except json.JSONDecodeError as exc:
				raise _invalid_row(path, line_number, "is not valid JSON") from exc
			if not isinstance(entry, dict):
				raise _invalid_row(path, line_number, "is not a JSON object")
			seq = _entry_seq(entry, path, line_number)
			if seq <= previous_seq:
				raise _invalid_row(
					path,
					line_number,
					f"has non-monotonic seq {seq} after {previous_seq}",
				)
			try:
				event = parse_event(entry)
			except (ValidationError, TypeError, ValueError) as exc:
				raise _invalid_row(path, line_number, "is not a valid event") from exc
			if not event.durable:
				raise _invalid_row(path, line_number, "contains a live-only event")
			# Return the validated canonical wire shape used by replay and the API.
			rows.append(event.model_dump(exclude_none=True))
			previous_seq = seq
	return rows


def _entry_seq(entry: dict, path: str, line_number: int) -> int:
	seq = entry.get("seq")
	if type(seq) is not int:
		raise _invalid_row(path, line_number, "is missing a valid integer seq")
	return seq


def _invalid_row(
	path: str,
	line_number: int,
	message: str,
) -> SessionLogError:
	return SessionLogError(f"Invalid session log {path}: line {line_number} {message}")
