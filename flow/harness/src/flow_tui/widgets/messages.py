"""Per-entry widgets: one durable transcript entry becomes one widget, plus the
mutable streamed-preview widget (`PartialAssistantView`) at the conversation tail.

`EntryView` is a container, not a single Static: an assistant message interleaves
text, thinking, and tool calls, and each thinking block folds to a one-word
marker that ctrl+t expands. A tool call renders as one `ToolCallView` — a per-tool one-liner
(`bash cmd`, `edit path (2 edits)`, …) that leads with the tool name. The matching
`ToolResult` merges into the same widget: the glyph clears (or settles to ✗), a bracket
suffix reports exit code / duration / truncation, and the output shows as a dim
few-line preview that ctrl+o expands. A diff in `ToolResult.details` gets syntax
highlighting instead of the plain preview.

Assistant text renders as Markdown once the durable message lands. The streamed
preview stays plain: a partial reply holds unclosed fences and half-written
tables, which reflow on every delta.
"""

from __future__ import annotations

import json

from rich.console import Group, RenderableType
from rich.syntax import Syntax
from rich.text import Text
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Markdown, Static

from flow_harness.events import (
	AssistantMessage,
	DisplaySegment,
	TextContent,
	ThinkingContent,
	ToolCall,
	ToolResult,
	TranscriptMessage,
	UserMessage,
)
from flow_harness.session.skills import parse_skill_invocation
from flow_tui.client.state import PartialPart, PartialText, PartialThinking, PartialToolCall
from flow_tui.theme import (
	STYLE_ERROR,
	STYLE_ERROR_STRONG,
	STYLE_MUTED,
	STYLE_RUNNING,
	STYLE_THINKING,
	STYLE_TOOL_NAME,
	SYNTAX_THEME,
)

SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_PREVIEW_LINES = 3
_DIFF_PREVIEW_LINES = 32
THINKING_MARKER = "Thinking… ctrl+t to expand"


def tool_label(name: str) -> Text:
	"""The tool name in its own style, so the eye splits the name from the arguments
	that follow it."""
	# the style rides on a span, not on the Text itself: a base style would bleed
	# into every argument appended after the name
	return Text().append(name, style=STYLE_TOOL_NAME)


def call_line(name: str, args: dict | None, display: list[DisplaySegment] | None = None) -> Text:
	"""Collapsed one-liner for a tool call with presentation-safe arguments."""
	if display:
		line = Text()
		for segment in display:
			line.append(segment.text, style=STYLE_TOOL_NAME if segment.arg is None else "")
		return line
	line = tool_label(name)
	if args is None:
		return line.append(" …", style=STYLE_MUTED)
	if name == "bash":
		return line.append(f" {args.get('command', '')}")
	if name == "edit":
		n = len(args.get("edits") or [])
		line.append(f" {args.get('path', '')}")
		return line.append(f" ({n} edit{'s' if n != 1 else ''})", style=STYLE_MUTED)
	if name == "write":
		line.append(f" {args.get('path', '')}")
		return line.append(f" ({len(args.get('content') or '')} chars)", style=STYLE_MUTED)
	if name == "read":
		return line.append(f" {args.get('path', '')}")
	if name == "grep":
		return line.append(f" {args.get('pattern', '')} {args.get('path', '')}".rstrip())
	if name == "subagent":
		return line.append(f" {args.get('description', '')}")
	if not args:
		return line
	return line.append(f" {json.dumps(args, ensure_ascii=False)}")


def result_line(result: ToolResult) -> Text:
	"""Fallback one-liner rebuilt from `details` for a result whose call was never
	seen (a replay hole); the call arguments are gone, the details survive."""
	d = result.details
	line = tool_label(result.name)
	if result.name == "bash" and d.get("command"):
		return line.append(f" {d['command']}")
	if result.name == "grep" and d.get("pattern"):
		line.append(f" {d['pattern']}")
	if d.get("path"):
		line.append(f" {d['path']}")
	if (n := d.get("edits")) is not None:
		line.append(f" ({n} edit{'s' if n != 1 else ''})", style=STYLE_MUTED)
	if (chars := d.get("chars")) is not None:
		line.append(f" ({chars} chars)", style=STYLE_MUTED)
	return line


def status_suffix(details: dict) -> str:
	"""Trailing bracket annotations from `details`: abort/timeout/exit code, duration,
	truncation, match count, spilled-output path."""
	parts: list[str] = []
	if details.get("aborted"):
		parts.append("aborted")
	elif details.get("timed_out"):
		parts.append("timed out")
	elif (code := details.get("exit_code")) is not None:
		parts.append(f"exit {code}")
	if (duration := details.get("duration_seconds")) is not None:
		parts.append(f"{duration}s")
	truncation = details.get("truncation") or {}
	if truncation.get("truncated"):
		shown, total = truncation.get("output_lines"), truncation.get("total_lines")
		parts.append(f"truncated · {shown}/{total} lines")
		if details.get("full_output_path"):
			parts.append(f"full output: {details['full_output_path']}")
	if (matches := details.get("matches")) is not None:
		parts.append(f"{matches} matches")
	return f"[{', '.join(parts)}]" if parts else ""


class ThinkingBlock(Static):
	"""One `ThinkingContent` block: a one-word marker until it expands.

	It carries no control of its own. ctrl+t drives every block at once, so a
	per-block toggle would let the transcript disagree with the keybind.
	"""

	collapsed: reactive[bool] = reactive(True)

	def __init__(self, thinking: str, *, collapsed: bool = True) -> None:
		super().__init__(classes="thinking")
		self.thinking = thinking
		self.set_reactive(ThinkingBlock.collapsed, collapsed)

	def render(self) -> RenderableType:
		return Text(THINKING_MARKER if self.collapsed else self.thinking, style=STYLE_THINKING)

	def watch_collapsed(self, _collapsed: bool) -> None:
		self.refresh(layout=True)


class ToolCallView(Static):
	"""One tool call and, once it merges in, its result.

	Runs through three looks: a spinner one-liner while the call executes, a settled
	unmarked line with a bracket suffix when the result lands, and — via the `expanded`
	reactive (ctrl+o) — the full output instead of the dim few-line preview.
	`call` is None when a result arrived without its call; the line then rebuilds
	from `ToolResult.details`.
	"""

	expanded: reactive[bool] = reactive(False)

	def __init__(
		self,
		call: ToolCall | None,
		*,
		entry_seq: int | None,
		result: ToolResult | None = None,
		expanded: bool = False,
		running: bool = True,
	) -> None:
		super().__init__(classes="tool-call")
		self.call = call
		self.entry_seq = entry_seq
		self.result = result
		self.result_seq = result.seq if result is not None else None
		self._live = running
		self._frame = 0
		self.set_reactive(ToolCallView.expanded, expanded)

	def on_mount(self) -> None:
		self.set_interval(0.1, self._tick)

	def render(self) -> RenderableType:
		header = self._header()
		body = self._body()
		return header if body is None else Group(header, body)

	def set_result(self, result: ToolResult) -> None:
		self.result = result
		self.result_seq = result.seq
		self.refresh(layout=True)

	def clear_result(self) -> None:
		"""A rewind cut the result but kept the call: back to the unresolved look."""
		self.result = None
		self.result_seq = None
		self.refresh(layout=True)

	def set_running(self, running: bool) -> None:
		"""Freeze or resume the spinner; a resultless call after the run ended shows a
		quiet dot instead of spinning forever."""
		if running != self._live:
			self._live = running
			self.refresh()

	def watch_expanded(self, _expanded: bool) -> None:
		self.refresh(layout=True)

	def _tick(self) -> None:
		if self.result is None and self._live:
			self._frame = (self._frame + 1) % len(SPINNER_FRAMES)
			self.refresh()

	def _header(self) -> Text:
		result = self.result
		failed = result is not None and (result.is_error or result.details.get("aborted"))
		if result is None:
			glyph, style = (SPINNER_FRAMES[self._frame], STYLE_RUNNING) if self._live else ("·", STYLE_MUTED)
		elif failed:
			glyph, style = "✗", STYLE_ERROR_STRONG
		else:
			glyph, style = None, ""  # a settled call carries no mark, and no gutter for one
		if self.call is not None:
			line = call_line(self.call.name, self.call.arguments, self.call.display)
		else:
			assert result is not None  # a call-less view always carries its result
			line = result_line(result)
		if failed:
			line.stylize(STYLE_ERROR)  # the failure colour outranks the per-part styles
		text = Text()
		if glyph is not None:
			text.append(f"{glyph} ", style)
		text.append_text(line)
		if result is not None and (suffix := status_suffix(result.details)):
			text.append(f" {suffix}", style=STYLE_ERROR if failed else STYLE_MUTED)
		return text

	def _body(self) -> RenderableType | None:
		result = self.result
		if result is None:
			return None
		if diff := result.details.get("diff"):
			return _diff_body(diff, expanded=self.expanded)
		content = result.content.strip()
		if not content:
			return None
		if self.expanded:
			return Text(content)
		lines = content.splitlines()
		head = lines[:_PREVIEW_LINES]
		if (hidden := len(lines) - len(head)) > 0:
			head.append(f"… (+{hidden} lines, ctrl+o to expand)")
		return Text("\n".join(head), style=STYLE_MUTED)


def _diff_body(diff: str, *, expanded: bool) -> RenderableType:
	lines = diff.splitlines()
	if expanded or len(lines) <= _DIFF_PREVIEW_LINES:
		return Syntax(diff, "diff", theme=SYNTAX_THEME)
	return Group(
		Syntax(
			"\n".join(lines[:_DIFF_PREVIEW_LINES]),
			"diff",
			theme=SYNTAX_THEME,
		),
		Text(f"… (+{len(lines) - _DIFF_PREVIEW_LINES} more diff lines, ctrl+o to expand)", style=STYLE_MUTED),
	)


class EntryView(Vertical):
	"""A rendered durable entry; keeps its seq so a rewind can drop it.

	`tool_calls` maps call id -> `ToolCallView` for the calls this entry contains, so
	the conversation can merge later `ToolResult` entries into them.
	"""

	def __init__(
		self,
		entry: TranscriptMessage,
		*,
		steered: bool = False,
		show_thinking: bool = False,
		expand_tools: bool = False,
		running: bool = True,
	) -> None:
		super().__init__()
		self.seq = entry.seq
		self.add_class(f"entry--{entry.type}")
		if steered:
			self.add_class("entry--steered")
		if entry.subagent_id is not None:
			self.add_class("entry--subagent")
		self._parts = entry_widgets(
			entry,
			steered=steered,
			show_thinking=show_thinking,
			expand_tools=expand_tools,
			running=running,
		)
		self.tool_calls = {
			part.call.id: part
			for part in self._parts
			if isinstance(part, ToolCallView) and part.call is not None
		}

	def compose(self):
		yield from self._parts


class PartialAssistantView(Static):
	"""The streamed preview: re-rendered on every delta, swapped out when the durable
	`assistant_message` arrives."""

	def update_parts(self, parts: list[PartialPart], *, show_thinking: bool = False) -> None:
		text = Text()
		for part in parts:
			if isinstance(part, PartialToolCall) and part.arguments is None:
				continue
			if text:
				text.append("\n")
			if isinstance(part, PartialThinking):
				if show_thinking:
					text.append(part.thinking, style=STYLE_THINKING)
				else:
					text.append(THINKING_MARKER, style=STYLE_THINKING)
			elif isinstance(part, PartialText):
				text.append(part.text)
			elif isinstance(part, PartialToolCall):
				text.append_text(call_line(part.name, part.arguments, part.display))
		text.append("▌", style=STYLE_MUTED)
		self.update(text)


def entry_widgets(
	entry: TranscriptMessage,
	*,
	steered: bool = False,
	show_thinking: bool = False,
	expand_tools: bool = False,
	running: bool = True,
) -> list[Widget]:
	if isinstance(entry, UserMessage):
		return [Static(_render_user(entry, steered=steered))]
	if isinstance(entry, AssistantMessage):
		return _assistant_widgets(
			entry, show_thinking=show_thinking, expand_tools=expand_tools, running=running
		)
	# a result whose call was never rendered (replay hole): standalone, already settled
	return [ToolCallView(None, entry_seq=entry.seq, result=entry, expanded=expand_tools, running=False)]


def _render_user(message: UserMessage, *, steered: bool) -> Text:
	# the tinted background marks a user entry, so a prompt glyph adds nothing
	invocation = parse_skill_invocation(message.text)
	if invocation is not None:
		body = f"Using skill: {', '.join(skill.name for skill in invocation.skills)}"
		if invocation.instructions:
			body += f"\n{invocation.instructions}"
	else:
		body = message.text
	if message.attachments:
		labels = " ".join(f"[{item.name}]" for item in message.attachments)
		body = f"{body}\n{labels}" if body else labels
	text = Text(body)
	if steered:
		text.append("  (steered)", style=STYLE_MUTED)
	return text


def _assistant_widgets(
	message: AssistantMessage, *, show_thinking: bool, expand_tools: bool, running: bool
) -> list[Widget]:
	widgets: list[Widget] = []
	for block in message.content:
		if isinstance(block, ThinkingContent):
			if block.redacted:
				widgets.append(Static(Text("Thinking · redacted", style=STYLE_THINKING)))
			elif block.thinking:
				# opaque reasoning with no summary has nothing worth a fold
				widgets.append(ThinkingBlock(block.thinking, collapsed=not show_thinking))
		elif isinstance(block, TextContent):
			widgets.append(Markdown(block.text))
		elif isinstance(block, ToolCall):
			widgets.append(ToolCallView(block, entry_seq=message.seq, expanded=expand_tools, running=running))
	if message.stop_reason in ("aborted", "error"):
		note = Text(f"[{message.stop_reason}]", style=STYLE_ERROR_STRONG)
		if message.error_message:
			note.append(f" {message.error_message}", style=STYLE_ERROR)
		widgets.append(Static(note))
	return widgets
