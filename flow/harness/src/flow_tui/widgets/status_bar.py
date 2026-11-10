"""One-line session status with model selection aligned on the right."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rich.text import Text
from textual import events
from textual.widgets import Static

from flow_tui.client.state import ConversationState


def compact_number(value: int) -> str:
	for threshold, suffix in ((1_000_000, "M"), (1_000, "k")):
		if value >= threshold:
			scaled = value / threshold
			return f"{scaled:.1f}".rstrip("0").rstrip(".") + suffix
	return str(value)


def repository_label(cwd: str | Path | None) -> str:
	path = Path(cwd or Path.cwd())
	result = subprocess.run(
		["git", "-C", str(path), "symbolic-ref", "--short", "HEAD"],
		capture_output=True,
		text=True,
		check=False,
	)
	branch = result.stdout.strip() if result.returncode == 0 else ""
	if not branch:
		return path.name
	dirty = subprocess.run(
		["git", "-C", str(path), "status", "--porcelain"],
		capture_output=True,
		text=True,
		check=False,
	).stdout.strip()
	return f"{path.name} ({branch}{'*' if dirty else ''})"


class StatusBar(Static):
	_left = ""
	_right = ""

	def refresh_from(self, state: ConversationState, *, queued: int = 0) -> None:
		if state.pending_approval is not None:
			run_state = "paused — awaiting approval"
		elif state.running:
			run_state = "running"
		else:
			run_state = "idle"

		window = compact_number(state.context_window) if state.context_window is not None else "?"
		parts = [
			repository_label(state.cwd),
			run_state,
			f"{compact_number(state.context_tokens)}/{window}",
			f"↑{compact_number(state.input_tokens)}",
			f"↓{compact_number(state.output_tokens)}",
		]
		if state.cache_read_tokens or state.cache_write_tokens:
			cache = []
			if state.cache_read_tokens:
				cache.append(f"R{compact_number(state.cache_read_tokens)}")
			if state.cache_write_tokens:
				cache.append(f"W{compact_number(state.cache_write_tokens)}")
			parts.append("⚡" + "/".join(cache))
		if queued:
			parts.append(f"{queued} queued")
		if state.retry is not None:
			retry = f"retrying {state.retry.attempt}"
			if state.retry.max_attempts:
				retry += f"/{state.retry.max_attempts}"
			if state.retry.delay_seconds:
				retry += f" in {state.retry.delay_seconds:.0f} s"
			parts.append(retry)
		self._left = " · ".join(parts)
		self._right = " · ".join((state.model or "?", state.reasoning_effort or "default"))
		self._update_line()

	def on_resize(self, _: events.Resize) -> None:
		self._update_line()

	def _update_line(self) -> None:
		width = self.content_size.width
		if width <= 0:
			line = f"{self._left} · {self._right}"
		elif width > len(self._right):
			left = self._left[: width - len(self._right) - 1]
			line = left + " " * (width - len(left) - len(self._right)) + self._right
		else:
			line = self._right[-width:]
		self.update(Text(line))
