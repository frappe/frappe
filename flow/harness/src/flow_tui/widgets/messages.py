"""Per-entry widgets: one durable transcript entry becomes one widget, plus the
mutable streamed-preview widget (`PartialAssistantView`) at the conversation tail.

Rendering stays deliberately plain for the MVP: thinking is dimmed text, tool calls
are one-liners, tool results show a short preview. Phase 8 upgrades these in place
(collapsible thinking, diff highlighting) without changing the widget boundaries.
"""

from __future__ import annotations

import json

from rich.text import Text
from textual.widgets import Static

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

_PREVIEW_CHARS = 400
_PREVIEW_LINES = 6
_ARGS_CHARS = 100


class EntryView(Static):
	"""A rendered durable entry; keeps its seq so a rewind can drop it."""

	def __init__(self, entry: TranscriptMessage, *, steered: bool = False) -> None:
		super().__init__(render_entry(entry, steered=steered))
		self.seq = entry.seq
		self.add_class(f"entry--{entry.type}")
		if steered:
			self.add_class("entry--steered")


class PartialAssistantView(Static):
	"""The streamed preview: re-rendered on every delta, swapped out when the durable
	`assistant_message` arrives."""

	def update_parts(self, parts: list[PartialPart]) -> None:
		text = Text()
		for part in parts:
			if text:
				text.append("\n")
			if isinstance(part, PartialThinking):
				text.append(part.thinking, style="dim italic")
			elif isinstance(part, PartialText):
				text.append(part.text)
			elif isinstance(part, PartialToolCall):
				text.append(f"⚙ {part.name}…", style="yellow")
		text.append("▌", style="dim")
		self.update(text)


def render_entry(entry: TranscriptMessage, *, steered: bool = False) -> Text:
	if isinstance(entry, UserMessage):
		return _render_user(entry, steered=steered)
	if isinstance(entry, AssistantMessage):
		return _render_assistant(entry)
	return _render_tool_result(entry)


def _render_user(message: UserMessage, *, steered: bool) -> Text:
	text = Text()
	text.append("↪ " if steered else "❯ ", style="bold cyan")  # noqa: RUF001
	text.append(message.content)
	if steered:
		text.append("  (steered)", style="dim")
	return text


def _render_assistant(message: AssistantMessage) -> Text:
	text = Text()
	for block in message.content:
		if text:
			text.append("\n")
		if isinstance(block, ThinkingContent):
			thinking = "[redacted thinking]" if block.redacted else block.thinking
			text.append(thinking, style="dim italic")
		elif isinstance(block, TextContent):
			text.append(block.text)
		elif isinstance(block, ToolCall):
			text.append(_tool_call_line(block), style="yellow")
	if message.stop_reason in ("aborted", "error"):
		if text:
			text.append("\n")
		text.append(f"[{message.stop_reason}]", style="bold red")
		if message.error_message:
			text.append(f" {message.error_message}", style="red")
	return text


def _render_tool_result(result: ToolResult) -> Text:
	text = Text()
	if result.is_error:
		text.append("✗ ", style="bold red")
	else:
		text.append("✓ ", style="bold green")
	text.append(result.name, style="yellow")
	preview = _preview(result.content)
	if preview:
		text.append("\n")
		text.append(preview, style="dim")
	return text


def _tool_call_line(call: ToolCall) -> str:
	args = json.dumps(call.arguments, ensure_ascii=False)
	if len(args) > _ARGS_CHARS:
		args = args[: _ARGS_CHARS - 1] + "…"
	return f"⚙ {call.name} {args}"


def _preview(content: str) -> str:
	lines = content.strip().splitlines()
	preview = "\n".join(lines[:_PREVIEW_LINES])
	if len(preview) > _PREVIEW_CHARS:
		preview = preview[:_PREVIEW_CHARS]
	if len(lines) > _PREVIEW_LINES or len(preview) < len(content.strip()):
		preview += " …"
	return preview
