"""Append-only audit trail of sensitive API calls (`ServerPolicy.audit_log`)."""

from __future__ import annotations

import json
import os
import time


class AuditLog:
	"""One JSONL row per audited request: ts, method, path, status, and the
	authenticated site in multi-tenant mode. Bodies are never recorded, so no
	secret can land here. A failed write is dropped — auditing must not take
	the daemon down."""

	def __init__(self, path: str):
		self.path = path

	def record(self, *, method: str, path: str, status: int, site: str | None = None) -> None:
		row: dict = {"ts": time.time(), "method": method, "path": path, "status": status}
		if site:
			row["site"] = site
		line = json.dumps(row) + "\n"
		try:
			fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
			try:
				os.write(fd, line.encode())
			finally:
				os.close(fd)
		except OSError:
			pass
