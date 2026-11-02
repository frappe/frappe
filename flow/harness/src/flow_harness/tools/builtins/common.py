"""Shared helpers for the builtin tools: path resolution, line-ending handling,
line+byte output truncation, temp-file spill, and process-group kill."""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import tempfile

from flow_harness.path_policy import absolute_path, canonical_path, is_path_allowed
from flow_harness.tools.tool import ToolContext

DEFAULT_MAX_LINES = 2000
DEFAULT_MAX_BYTES = 50 * 1024


def resolve(ctx: ToolContext, path: str, *, read_only: bool = False) -> str:
	target = absolute_path(path, base=ctx.cwd)
	if ctx.allowed_roots:
		roots = (*ctx.allowed_roots, *ctx.read_only_roots) if read_only else ctx.allowed_roots
		if not is_path_allowed(canonical_path(target), roots, ignore_hidden_files=ctx.ignore_hidden_files):
			raise PermissionError(f"path {path!r} resolves outside the configured allowed roots")
	return target


def to_lf(text: str) -> str:
	return text.replace("\r\n", "\n").replace("\r", "\n")


def detect_ending(text: str) -> str:
	i = text.find("\n")
	return "\r\n" if i > 0 and text[i - 1] == "\r" else "\n"


def truncate(
	text: str, *, keep: str, max_lines: int = DEFAULT_MAX_LINES, max_bytes: int = DEFAULT_MAX_BYTES
) -> tuple[str, dict]:
	"""Clip `text` to the line+byte budget, keeping the head or tail. Returns the
	clipped text plus truncation metadata for a tool result's `details`."""
	lines = text.split("\n")
	total_lines = len(lines)
	total_bytes = len(text.encode())
	if total_lines <= max_lines and total_bytes <= max_bytes:
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
		if len(picked) >= max_lines:
			truncated_by = "lines"
			break
		add = len(line.encode()) + (1 if picked else 0)
		if used + add > max_bytes:
			truncated_by = "bytes"
			break
		picked.append(line)
		used += add
	room = max_bytes - used - (1 if picked else 0)
	if truncated_by == "bytes" and room > 0 and (keep == "tail" or not picked):
		edge = seq[len(picked)].encode()
		picked.append((edge[:room] if keep == "head" else edge[-room:]).decode("utf-8", "ignore"))
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
