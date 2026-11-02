"""Bench-style terminal logging for the serving daemon.

One `HH:MM:SS message` line per record on stderr — the level named (and colored)
only when it is a warning or worse — plus one `uvicorn.access` line per request."""

from __future__ import annotations

import logging
import sys
import time

DIM = "\033[2m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"

_LEVEL_COLORS = {"WARNING": YELLOW, "ERROR": RED, "CRITICAL": RED}


class _TerminalFormatter(logging.Formatter):
	def __init__(self, color: bool = True) -> None:
		super().__init__("%(message)s")
		self._color = color

	def format(self, record: logging.LogRecord) -> str:
		body = super().format(record)  # appends exception text when present
		stamp = time.strftime("%H:%M:%S", time.localtime(record.created))
		if self._color:
			stamp = f"{DIM}{stamp}{RESET}"
		if record.levelno < logging.WARNING:
			return f"{stamp} {body}"
		level = record.levelname.lower()
		if self._color:
			level = f"{_LEVEL_COLORS.get(record.levelname, '')}{level}{RESET}"
		return f"{stamp} {level} {body}"


def setup_terminal_logging() -> None:
	"""Route the daemon's records to stderr: libraries at warning and up, one
	access line per request. Pass `log_config=None` to uvicorn so this stands."""
	handler = logging.StreamHandler()
	# color codes only for a live terminal, never into a redirected log file
	handler.setFormatter(_TerminalFormatter(color=sys.stderr.isatty()))
	root = logging.getLogger()
	root.handlers[:] = [handler]
	root.setLevel(logging.WARNING)
	logging.getLogger("uvicorn.access").setLevel(logging.INFO)
	# litellm's own logger chats at info; warnings only
	logging.getLogger("LiteLLM").setLevel(logging.WARNING)
