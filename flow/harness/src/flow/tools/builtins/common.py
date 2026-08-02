"""Shared helpers for the builtin tools: path resolution, line-ending handling,
line+byte output truncation, temp-file spill, and process-group kill."""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import tempfile

from flow.path_policy import absolute_path, canonical_path, is_path_allowed
from flow.tools.tool import ToolContext

DEFAULT_MAX_LINES = 2000
DEFAULT_MAX_BYTES = 50 * 1024


def resolve(ctx: ToolContext, path: str) -> str:
	target = absolute_path(path, base=ctx.cwd)
	if ctx.allowed_roots and not is_path_allowed(canonical_path(target), ctx.allowed_roots):
		raise PermissionError(f"path {path!r} resolves outside the configured allowed roots")
	return target


def to_lf(text: str) -> str:
	return text.replace("\r\n", "\n").replace("\r", "\n")


def detect_ending(text: str) -> str:
	i = text.find("\n")
	return "\r\n" if i > 0 and text[i - 1] == "\r" else "\n"


def truncate(text: str, *, keep: str) -> tuple[str, dict]:
	"""Clip `text` to the line+byte budget, keeping the head or tail. Returns the
	clipped text plus truncation metadata for a tool result's `details`."""
	lines = text.split("\n")
	total_lines = len(lines)
	total_bytes = len(text.encode())
	if total_lines <= DEFAULT_MAX_LINES and total_bytes <= DEFAULT_MAX_BYTES:
		return text, {
			"truncated": False,
			"truncated_by": None,
			"total_lines": total_lines,
			"output_lines": total_lines,
			"total_bytes": total_bytes,
		}

	seq = lines if keep == "head" else list(reversed(lines))
	picked: list[str] = []
	used = 0
	truncated_by = "lines"
	for line in seq:
		if len(picked) >= DEFAULT_MAX_LINES:
			truncated_by = "lines"
			break
		add = len(line.encode()) + (1 if picked else 0)
		if used + add > DEFAULT_MAX_BYTES:
			truncated_by = "bytes"
			break
		picked.append(line)
		used += add
	if not picked:  # a single line exceeds the byte budget on its own
		picked = [seq[0].encode()[:DEFAULT_MAX_BYTES].decode("utf-8", "ignore")]
		truncated_by = "bytes"
	if keep == "tail":
		picked.reverse()
	return "\n".join(picked), {
		"truncated": True,
		"truncated_by": truncated_by,
		"total_lines": total_lines,
		"output_lines": len(picked),
		"total_bytes": total_bytes,
	}


def spill(text: str) -> str:
	"""Write full output to a temp file and return its path (for truncated results)."""
	fd, path = tempfile.mkstemp(prefix="flow-bash-", suffix=".log")
	with os.fdopen(fd, "w", encoding="utf-8") as f:
		f.write(text)
	return path


def kill_group(proc: asyncio.subprocess.Process) -> None:
	with contextlib.suppress(ProcessLookupError):
		os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
