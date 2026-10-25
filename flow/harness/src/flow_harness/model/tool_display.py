"""Tool-call display rendering shared by the streaming adapters: safe string
metadata and templated display segments, from partial or complete arguments."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic_core import from_json

from flow_harness.events import AssistantMessage, DisplaySegment, ToolCall, ToolCallDisplayReady
from flow_harness.tools.tool import DISPLAY_VALUE_CHARS, display_template_variables, render_tool_display

_TOOL_METADATA_PREFIX_CHARS = 4096


def _tool_call_arguments(
	arguments: str | Mapping[str, Any], *, complete: bool = False
) -> Mapping[str, Any] | None:
	if not isinstance(arguments, str):
		return arguments
	if not arguments:
		return {}
	try:
		parsed = from_json(
			arguments if complete else arguments[:_TOOL_METADATA_PREFIX_CHARS],
			allow_partial=not complete,
		)
	except ValueError:
		return None
	return parsed if isinstance(parsed, Mapping) else None


def extract_tool_call_display_metadata(
	arguments: str | Mapping[str, Any], *, allow_empty: bool = False
) -> dict[str, str] | None:
	"""Extract complete top-level strings from a bounded prefix of streamed JSON.

	Labels need small fields such as ``path`` or ``command``, not a second copy of a
	potentially large edit payload. Partial parsing exposes those fields as soon as
	their string closes while the prefix bound keeps repeated chunk handling cheap.
	"""
	parsed = _tool_call_arguments(arguments)
	if parsed is None:
		return None
	metadata = {
		str(key): value[:DISPLAY_VALUE_CHARS]
		for key, value in parsed.items()
		if isinstance(value, str) and value
	}
	return metadata if metadata or allow_empty else None


def _render_parsed_tool_display(
	template: str, arguments: Mapping[str, Any], *, partial: bool
) -> list[DisplaySegment] | None:
	# Partial JSON parsing reliably tells us when a string closes. Numbers and
	# containers can still grow in a later chunk, so render those only from a
	# complete payload (or an already-materialized mapping, as used by MockModel).
	if partial:
		for name in display_template_variables(template):
			if name in arguments and not isinstance(arguments[name], str):
				return None
	return render_tool_display(template, dict(arguments))


def tool_call_display_ready_event(
	call_id: str,
	name: str,
	arguments: str | Mapping[str, Any],
	*,
	display_template: str | None = None,
	complete: bool = False,
) -> ToolCallDisplayReady | None:
	"""Build the first useful live event for a streamed tool call."""
	if not call_id or not name:
		return None
	complete = complete or not isinstance(arguments, str)
	parsed = _tool_call_arguments(arguments, complete=complete)
	if parsed is None:
		if not complete:
			return None
		# Preserve any safe string metadata from a malformed final payload. The
		# durable ToolCall will carry the provider parse error.
		metadata = extract_tool_call_display_metadata(arguments, allow_empty=True)
		if metadata is None:
			return None
		return ToolCallDisplayReady(id=call_id, name=name, arguments=metadata)

	display = None
	if display_template is not None:
		display = _render_parsed_tool_display(
			display_template,
			parsed,
			partial=isinstance(arguments, str) and not complete,
		)
		if display is None and not complete:
			return None
	metadata = extract_tool_call_display_metadata(parsed, allow_empty=complete or display is not None)
	if metadata is None:
		return None
	return ToolCallDisplayReady(id=call_id, name=name, arguments=metadata, display=display)


def with_tool_call_displays(message: AssistantMessage, templates: Mapping[str, str]) -> AssistantMessage:
	"""Render configured display text onto the durable tool calls in a message."""
	content = None
	for index, block in enumerate(message.content):
		if not isinstance(block, ToolCall) or block.error is not None:
			continue
		template = templates.get(block.name)
		if template is None:
			continue
		display = render_tool_display(template, block.arguments)
		if display == block.display:
			continue
		if content is None:
			content = list(message.content)
		content[index] = block.model_copy(update={"display": display})
	return message if content is None else message.model_copy(update={"content": content})
