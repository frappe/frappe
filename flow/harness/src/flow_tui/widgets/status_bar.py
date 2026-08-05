"""One-line session status: model · effort · state · tokens · cost · session id."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rich.text import Text
from textual.widgets import Static

from flow_tui.client.state import ConversationState


def repository_label(cwd: str | Path | None) -> str:
	path = Path(cwd or Path.cwd())
	result = subprocess.run(
		["git", "-C", str(path), "symbolic-ref", "--short", "HEAD"],
		capture_output=True,
		text=True,
		check=False,
	)
	branch = result.stdout.strip() if result.returncode == 0 else ""
	return f"{path.name} ({branch})" if branch else path.name


class StatusBar(Static):
	def refresh_from(
		self, state: ConversationState, *, session_id: str | None = None, queued: int = 0
	) -> None:
		if state.pending_approval is not None:
			run_state = "paused — awaiting approval"
		elif state.running:
			run_state = "running"
		else:
			run_state = "idle"

		parts = [
			repository_label(state.cwd),
			state.model or "?",
			f"effort: {state.reasoning_effort or 'default'}",
			run_state,
			f"Σ {state.input_tokens + state.output_tokens} tok",
			f"${state.cost:.4f}",
		]
		if queued:
			parts.append(f"{queued} queued")
		if state.retry is not None:
			retry = f"retrying {state.retry.attempt}"
			if state.retry.max_attempts:
				retry += f"/{state.retry.max_attempts}"
			if state.retry.delay_seconds:
				retry += f" in {state.retry.delay_seconds:.0f} s"
			parts.append(retry)
		if session_id:
			parts.append(session_id[:8])
		self.update(Text(" · ".join(parts)))
