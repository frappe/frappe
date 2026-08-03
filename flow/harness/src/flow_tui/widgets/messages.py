"""Per-entry widgets: one durable transcript entry becomes one widget, plus the
mutable streamed-preview widget (`PartialAssistantView`) at the conversation tail.

`EntryView` is a container, not a single Static: an assistant message interleaves
text, thinking, and tool calls, and each thinking block folds behind its own
`Collapsible`. Tool results dispatch on `ToolResult.details` — a diff gets syntax
highlighting, exit code and truncation become header badges, and everything else
falls back to a collapsed output preview.
"""

from __future__ import annotations

import json

from rich.syntax import Syntax
from rich.text import Text
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Collapsible, Static

from flow.events import (
	AssistantMessage,
	TextContent,
	ThinkingContent,
	ToolCall,
	ToolResult,
	TranscriptMessage,
	UserMessage,
)
from flow_tui.client.state import PartialPart, PartialText, PartialThinking, PartialToolCall

_TITLE_CHARS = 60
_ARGS_CHARS = 100


class ThinkingBlock(Collapsible):
	"""One `ThinkingContent` block, folded behind a char-count title."""

	def __init__(self, thinking: str, *, collapsed: bool = True) -> None:
		super().__init__(
			Static(Text(thinking, style="dim italic")),
			title=f"thinking · {len(thinking)} chars",
			collapsed=collapsed,
		)


class EntryView(Vertical):
	"""A rendered durable entry; keeps its seq so a rewind can drop it."""

	def __init__(
		self, entry: TranscriptMessage, *, steered: bool = False, show_thinking: bool = False
	) -> None:
		super().__init__()
		self.seq = entry.seq
		self.add_class(f"entry--{entry.type}")
		if steered:
			self.add_class("entry--steered")
		self._parts = entry_widgets(entry, steered=steered, show_thinking=show_thinking)

	def compose(self):
		yield from self._parts


class PartialAssistantView(Static):
	"""The streamed preview: re-rendered on every delta, swapped out when the durable
	`assistant_message` arrives."""

	def update_parts(self, parts: list[PartialPart], *, show_thinking: bool = False) -> None:
		text = Text()
		for part in parts:
			if text:
				text.append("\n")
			if isinstance(part, PartialThinking):
				if show_thinking:
					text.append(part.thinking, style="dim italic")
				else:
					text.append(f"thinking · {len(part.thinking)} chars", style="dim italic")
			elif isinstance(part, PartialText):
				text.append(part.text)
			elif isinstance(part, PartialToolCall):
				text.append(f"⚙ {part.name}…", style="yellow")
		text.append("▌", style="dim")
		self.update(text)


def entry_widgets(
	entry: TranscriptMessage, *, steered: bool = False, show_thinking: bool = False
) -> list[Widget]:
	if isinstance(entry, UserMessage):
		return [Static(_render_user(entry, steered=steered))]
	if isinstance(entry, AssistantMessage):
		return _assistant_widgets(entry, show_thinking=show_thinking)
	return _tool_result_widgets(entry)


def _render_user(message: UserMessage, *, steered: bool) -> Text:
	text = Text()
	text.append("↪ " if steered else "❯ ", style="bold cyan")  # noqa: RUF001
	text.append(message.content)
	if steered:
		text.append("  (steered)", style="dim")
	return text


def _assistant_widgets(message: AssistantMessage, *, show_thinking: bool) -> list[Widget]:
	widgets: list[Widget] = []
	for block in message.content:
		if isinstance(block, ThinkingContent):
			if block.redacted:
				sealed = Static(Text("thinking · redacted", style="dim italic"), classes="thinking--redacted")
				widgets.append(sealed)
			else:
				widgets.append(ThinkingBlock(block.thinking, collapsed=not show_thinking))
		elif isinstance(block, TextContent):
			widgets.append(Static(Text(block.text)))
		elif isinstance(block, ToolCall):
			widgets.append(Static(Text(_tool_call_line(block), style="yellow")))
	if message.stop_reason in ("aborted", "error"):
		note = Text(f"[{message.stop_reason}]", style="bold red")
		if message.error_message:
			note.append(f" {message.error_message}", style="red")
		widgets.append(Static(note))
	return widgets


def _tool_result_widgets(result: ToolResult) -> list[Widget]:
	widgets: list[Widget] = [Static(_tool_result_header(result))]
	diff = result.details.get("diff")
	if diff:
		body = Static(Syntax(diff, "diff", background_color="default"))
		widgets.append(Collapsible(body, title="diff", collapsed=False))
	elif content := result.content.strip():
		lines = content.splitlines()
		title = _clip(lines[0], _TITLE_CHARS)
		if len(lines) > 1:
			title += f" · {len(lines)} lines"
		widgets.append(Collapsible(Static(Text(content, style="dim")), title=title, collapsed=True))
	return widgets


def _tool_result_header(result: ToolResult) -> Text:
	text = Text()
	if result.is_error:
		text.append("✗ ", style="bold red")
	else:
		text.append("✓ ", style="bold green")
	text.append(result.name, style="yellow")
	if path := result.details.get("path"):
		text.append(f" {path}", style="dim")
	for badge, style in _badges(result.details):
		text.append(f"  [{badge}]", style=style)
	return text


def _badges(details: dict) -> list[tuple[str, str]]:
	"""Header badges for the `details` shapes the builtin tools emit."""
	badges: list[tuple[str, str]] = []
	if (code := details.get("exit_code")) is not None:
		badges.append((f"exit {code}", "green" if code == 0 else "red"))
	if details.get("aborted"):
		badges.append(("aborted", "red"))
	if details.get("timed_out"):
		badges.append(("timed out", "red"))
	truncation = details.get("truncation") or {}
	if truncation.get("truncated"):
		shown, total = truncation.get("output_lines"), truncation.get("total_lines")
		badges.append((f"truncated · {shown}/{total} lines", "yellow"))
	if (matches := details.get("matches")) is not None:
		badges.append((f"{matches} matches", "dim"))
	if (edits := details.get("edits")) is not None:
		badges.append((f"{edits} edit{'s' if edits != 1 else ''}", "dim"))
	if (chars := details.get("chars")) is not None:
		badges.append((f"{chars} chars", "dim"))
	return badges


def _tool_call_line(call: ToolCall) -> str:
	args = json.dumps(call.arguments, ensure_ascii=False)
	return f"⚙ {call.name} {_clip(args, _ARGS_CHARS)}"


def _clip(text: str, limit: int) -> str:
	return text if len(text) <= limit else text[: limit - 1] + "…"
