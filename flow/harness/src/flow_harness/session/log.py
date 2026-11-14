"""Append-only, sequence-numbered event log — the durable source of truth for a run.

Every durable event gets a monotonic `seq`. `read_since(n)` is both the replay path
(catch a reconnecting client up) and the restart path (rebuild state from disk).
"""

from __future__ import annotations

import json
import os
import threading
import time

from pydantic import ValidationError

from flow_harness.events import _Event, parse_event


class SessionLogError(ValueError):
	"""A persisted JSONL row violates the session-log contract.
	Carries the row's location so an operator can find it without re-reading the file."""

	def __init__(self, path: str, line: int, offset: int, reason: str):
		self.path = path
		self.line = line
		self.offset = offset
		self.reason = reason
		super().__init__(f"Invalid session log {path}: line {line} {reason} (byte offset {offset})")


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
			# default to the previous row; a rewound writer passes its own parent
			parent_seq = event.parent_seq if event.parent_seq is not None else self._seq
			persisted = event.model_copy(
				update={"seq": next_seq, "parent_seq": parent_seq, "ts": time.time()}
			)
			data = (persisted.model_dump_json(exclude_none=True) + "\n").encode()
			os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
			fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
			try:
				os.chmod(self.path, 0o600)
				complete = os.fstat(fd).st_size
				try:
					if os.write(fd, data) != len(data):
						raise OSError("short write while appending session log")
				except BaseException:
					# A partial line has no newline, so the next append would splice onto
					# it. Roll back to the last complete line instead.
					os.ftruncate(fd, complete)
					raise
			finally:
				os.close(fd)
			# only now is the line written, so only now does the sequence advance
			self._seq = next_seq
			event.seq = next_seq
			event.parent_seq = parent_seq
			event.ts = persisted.ts
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
	offset = 0
	with open(path, encoding="utf-8") as file:
		for line_number, line in enumerate(file, start=1):
			if line.strip():
				rows.append(_read_row(line, path, line_number, offset, previous_seq))
				previous_seq = rows[-1]["seq"]
			offset += len(line.encode())
	return rows


def _read_row(line: str, path: str, line_number: int, offset: int, previous_seq: int) -> dict:
	def invalid(reason: str) -> SessionLogError:
		return SessionLogError(path, line_number, offset, reason)

	try:
		entry = json.loads(line)
	except json.JSONDecodeError as exc:
		raise invalid("is not valid JSON") from exc
	if not isinstance(entry, dict):
		raise invalid("is not a JSON object")
	seq = entry.get("seq")
	if type(seq) is not int:
		raise invalid("is missing a valid integer seq")
	if seq <= previous_seq:
		raise invalid(f"has non-monotonic seq {seq} after {previous_seq}")
	try:
		event = parse_event(entry)
	except (ValidationError, TypeError, ValueError) as exc:
		raise invalid("is not a valid event") from exc
	if not event.durable:
		raise invalid("contains a live-only event")
	# Return the validated canonical wire shape used by replay and the API.
	return event.model_dump(exclude_none=True)
