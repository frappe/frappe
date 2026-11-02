"""Context compaction: estimate, choose a safe boundary, and summarize what falls off.

The design follows Pi's bounded standalone summary call and Tau's append-only fold,
adapted to Flow's event log: this module owns compaction planning and its balanced
start/end protocol; the transcript owns applying the durable `Compaction` row.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from flow_harness.events import (
	AnyEvent,
	AssistantMessage,
	Compaction,
	CompactionEnded,
	CompactionReason,
	CompactionStarted,
	ToolResult,
	TranscriptMessage,
	Usage,
	UserMessage,
)
from flow_harness.model.base import Model, ModelRequest
from flow_harness.model.cancellation import ModelCancelled, iterate_with_cancellation
from flow_harness.model.content import attachment_summary
from flow_harness.session.transcript import COMPACTION_SUMMARY_PREFIX

CHARS_PER_TOKEN = 4
MESSAGE_OVERHEAD_TOKENS = 4
TOOL_OVERHEAD_TOKENS = 16
DEFAULT_CONTEXT_WINDOW_TOKENS = 128_000
MAX_RESERVED_OUTPUT_TOKENS = 16_384
KEEP_RECENT_TOKENS = 20_000  # the tail an automatic compaction preserves
# Pi deliberately clips noisy tool data before summarization. The complete prompt is
# also budgeted below, so prose can use the model's available room instead of an
# arbitrary per-message cap.
MAX_TOOL_CONTENT_CHARS_IN_SUMMARY = 2_000
MAX_SUMMARY_INSTRUCTION_CHARS = 2_000
ESTIMATED_IMAGE_TOKENS = 6_000

SUMMARIZATION_SYSTEM_PROMPT = (
	"You are a context summarization assistant. Your task is to read a conversation "
	"between a user and an AI coding assistant, then produce a structured summary "
	"following the exact format specified.\n\n"
	"Do NOT continue the conversation. Do NOT respond to any questions in the "
	"conversation. ONLY output the structured summary."
)

SUMMARIZATION_PROMPT = (
	"The messages above are a conversation to summarize. Create a structured context "
	"checkpoint summary that another LLM will use to continue the work.\n\n"
	"Use this EXACT format:\n\n"
	"## Goal\n"
	"[What is the user trying to accomplish? Can be multiple items if the session "
	"covers different tasks.]\n\n"
	"## Constraints & Preferences\n"
	"- [Any constraints, preferences, or requirements mentioned by user]\n"
	'- [Or "(none)" if none were mentioned]\n\n'
	"## Progress\n"
	"### Done\n"
	"- [x] [Completed tasks/changes]\n\n"
	"### In Progress\n"
	"- [ ] [Current work]\n\n"
	"### Blocked\n"
	"- [Issues preventing progress, if any]\n\n"
	"## Key Decisions\n"
	"- **[Decision]**: [Brief rationale]\n\n"
	"## Next Steps\n"
	"1. [Ordered list of what should happen next]\n\n"
	"## Critical Context\n"
	"- [Any data, examples, or references needed to continue]\n"
	'- [Or "(none)" if not applicable]\n\n'
	"Keep each section concise. Preserve exact file paths, function names, and error "
	"messages."
)

UPDATE_SUMMARIZATION_PROMPT = (
	"The messages above are NEW conversation messages to incorporate into the existing "
	"summary provided in <previous-summary> tags.\n\n"
	"Update the existing structured summary with new information. RULES:\n"
	"- PRESERVE all existing information from the previous summary\n"
	"- ADD new progress, decisions, and context from the new messages\n"
	'- UPDATE the Progress section: move items from "In Progress" to "Done" when '
	"completed\n"
	'- UPDATE "Next Steps" based on what was accomplished\n'
	"- PRESERVE exact file paths, function names, and error messages\n"
	"- If something is no longer relevant, you may remove it\n\n"
	"Use this EXACT format:\n\n"
	"## Goal\n"
	"[Preserve existing goals, add new ones if the task expanded]\n\n"
	"## Constraints & Preferences\n"
	"- [Preserve existing, add new ones discovered]\n\n"
	"## Progress\n"
	"### Done\n"
	"- [x] [Include previously done items AND newly completed items]\n\n"
	"### In Progress\n"
	"- [ ] [Current work - update based on progress]\n\n"
	"### Blocked\n"
	"- [Current blockers - remove if resolved]\n\n"
	"## Key Decisions\n"
	"- **[Decision]**: [Brief rationale] (preserve all previous, add new)\n\n"
	"## Next Steps\n"
	"1. [Update based on current state]\n\n"
	"## Critical Context\n"
	"- [Preserve important context, add new if needed]\n\n"
	"Keep each section concise. Preserve exact file paths, function names, and error "
	"messages."
)


# --- compaction -------------------------------------------------------------


@dataclass(frozen=True)
class CompactionPlan:
	"""Messages selected for compaction and the durable sequence to compact up to.
	A previous summary travels separately so the summarizer can update it."""

	compact_up_to_seq: int
	messages_to_summarize: tuple[TranscriptMessage, ...]
	previous_summary: str | None


async def compact_events(
	model: Model,
	compaction_plan: CompactionPlan,
	*,
	compaction_reason: CompactionReason,
	cancellation: asyncio.Event | None,
	summary_instructions: str | None = None,
	resolve_attachment: Callable[[str], bytes] | None = None,
	params: Mapping[str, Any] | None = None,
) -> AsyncIterator[AnyEvent]:
	"""Summarize the plan and yield one balanced start/end protocol.

	The failure event is yielded before the exception is re-raised, so callers only
	choose whether a failed automatic attempt is fatal; they never repair the protocol.
	"""
	yield CompactionStarted(reason=compaction_reason)
	usage_seen: list[Usage] = []
	try:
		summary, usage = await summarize(
			model,
			compaction_plan,
			cancellation=cancellation,
			summary_instructions=summary_instructions,
			resolve_attachment=resolve_attachment,
			params=params,
			on_usage=usage_seen.append,
		)
	except Exception as error:
		if usage_seen:
			yield usage_seen[-1]
		yield CompactionEnded(
			reason=compaction_reason,
			error_message="aborted" if isinstance(error, ModelCancelled) else str(error),
		)
		raise
	yield Compaction(
		reason=compaction_reason,
		summary=summary,
		compact_up_to_seq=compaction_plan.compact_up_to_seq,
	)
	if usage is not None:
		yield usage  # after the row it paid for, so clients can attribute it there
	yield CompactionEnded(reason=compaction_reason)


async def summarize(
	model: Model,
	compaction_plan: CompactionPlan,
	*,
	cancellation: asyncio.Event | None,
	summary_instructions: str | None = None,
	resolve_attachment: Callable[[str], bytes] | None = None,
	params: Mapping[str, Any] | None = None,
	on_usage: Callable[[Usage], None] | None = None,
) -> tuple[str, Usage | None]:
	"""One standalone tool-less model call; deltas are consumed here, never yielded.
	Every prompt part is bounded to the model's window.

	Returns the summary and what the call cost, for the caller to log."""
	context_window_tokens = model.context_window or DEFAULT_CONTEXT_WINDOW_TOKENS
	reserved_output_tokens = calculate_reserved_output_tokens(context_window_tokens)
	max_summary_output_tokens = max(1, reserved_output_tokens * 4 // 5)
	model_max_output_tokens = model.max_output_tokens
	if model_max_output_tokens is not None and model_max_output_tokens > 0:
		max_summary_output_tokens = min(max_summary_output_tokens, model_max_output_tokens)
	bounded_compaction_plan = compaction_plan
	if compaction_plan.previous_summary is not None:
		bounded_compaction_plan = CompactionPlan(
			compact_up_to_seq=compaction_plan.compact_up_to_seq,
			messages_to_summarize=compaction_plan.messages_to_summarize,
			previous_summary=_fit_text(
				compaction_plan.previous_summary,
				max_summary_output_tokens * CHARS_PER_TOKEN,
			),
		)
	max_summary_prompt_tokens = (
		calculate_compaction_input_limit(model)
		- estimate_text_tokens(SUMMARIZATION_SYSTEM_PROMPT)
		- MESSAGE_OVERHEAD_TOKENS
	)
	summary_prompt = build_summary_prompt(
		bounded_compaction_plan,
		summary_instructions,
		max_summary_prompt_tokens=max_summary_prompt_tokens,
		resolve_attachment=resolve_attachment,
	)
	summary_request = ModelRequest(
		messages=[UserMessage(content=summary_prompt)],
		system_prompt=SUMMARIZATION_SYSTEM_PROMPT,
		stream=False,
		cancellation=cancellation,
		max_output_tokens=max_summary_output_tokens,
		params=params,
	)
	summary_response: AssistantMessage | None = None
	summary_usage: Usage | None = None
	async for response_event in iterate_with_cancellation(model.run(summary_request), cancellation):
		if isinstance(response_event, AssistantMessage):
			summary_response = response_event
		elif isinstance(response_event, Usage):
			# this prompt is the transcript being summarized, not the conversation itself
			summary_usage = response_event.model_copy(update={"standalone": True})
			if on_usage is not None:
				on_usage(summary_usage)
	if summary_response is None:
		raise RuntimeError("summarization ended without an assistant message")
	if summary_response.stop_reason == "aborted":
		raise ModelCancelled
	if summary_response.stop_reason == "error":
		raise RuntimeError(summary_response.error_message or "summarization failed")
	generated_summary = summary_response.text.strip()
	if not generated_summary:
		raise RuntimeError("summarization returned an empty summary")
	# Native adapters may not expose an output-limit control. Keep the durable
	# summary bounded even when the provider ignores the requested cap.
	return _fit_text(generated_summary, max_summary_output_tokens * CHARS_PER_TOKEN), summary_usage


def calculate_compaction_input_limit(model: Model) -> int:
	"""Input budget that leaves output room inside the model's context window."""
	context_window_tokens = model.context_window or DEFAULT_CONTEXT_WINDOW_TOKENS
	reserved_output_tokens = calculate_reserved_output_tokens(context_window_tokens)
	return max(1, context_window_tokens - reserved_output_tokens)


def calculate_reserved_output_tokens(context_window_tokens: int) -> int:
	"""Output room held back from the window; proportional for small windows."""
	return min(MAX_RESERVED_OUTPUT_TOKENS, max(1, context_window_tokens // 4))


# --- planning ---------------------------------------------------------------


def plan_keep_recent(
	messages: Sequence[TranscriptMessage], keep_recent_tokens: int = KEEP_RECENT_TOKENS
) -> CompactionPlan | None:
	"""Summarize everything except roughly the newest `keep_recent_tokens`.

	The kept tail starts on a user message when possible, else on an assistant
	message (the summary supplies its context) — never on a bare tool result.
	"""
	if len(messages) < 2:
		return None
	first_kept_message_index = _first_kept_message_index(messages, keep_recent_tokens)
	if first_kept_message_index <= 0:
		return None
	return _build_compaction_plan(messages[:first_kept_message_index])


def plan_all(messages: Sequence[TranscriptMessage]) -> CompactionPlan | None:
	"""Plan to compact the whole conversation (the manual `/compact`)."""
	if not messages:
		return None
	return _build_compaction_plan(messages)


def _build_compaction_plan(
	messages_to_compact: Sequence[TranscriptMessage],
) -> CompactionPlan | None:
	compact_up_to_seq = max((m.seq for m in messages_to_compact if m.seq is not None), default=0)
	if compact_up_to_seq <= 0:
		return None
	previous_summary, messages_to_summarize = _split_previous_summary(messages_to_compact)
	return CompactionPlan(
		compact_up_to_seq=compact_up_to_seq,
		messages_to_summarize=tuple(messages_to_summarize),
		previous_summary=previous_summary,
	)


def _split_previous_summary(
	messages_to_compact: Sequence[TranscriptMessage],
) -> tuple[str | None, Sequence[TranscriptMessage]]:
	first = messages_to_compact[0]
	if isinstance(first, UserMessage) and first.text.startswith(COMPACTION_SUMMARY_PREFIX):
		return first.text.removeprefix(COMPACTION_SUMMARY_PREFIX), messages_to_compact[1:]
	return None, messages_to_compact


def _first_kept_message_index(messages: Sequence[TranscriptMessage], keep_recent_tokens: int) -> int:
	"""Walk backward to the target, then snap forward to a safe message boundary."""
	if keep_recent_tokens <= 0:
		return len(messages)

	recent_message_tokens = 0
	candidate_index: int | None = None
	for index in range(len(messages) - 1, -1, -1):
		recent_message_tokens += estimate_message_tokens(messages[index])
		if recent_message_tokens >= keep_recent_tokens:
			candidate_index = index
			break
	if candidate_index is None:
		return 0

	if isinstance(messages[candidate_index], UserMessage):
		if candidate_index > 0:
			return candidate_index
		next_user_message_index = _next_user_message_index(messages, start=1)
		return next_user_message_index if next_user_message_index is not None else 0
	next_user_message_index = _next_user_message_index(messages, start=candidate_index + 1)
	if next_user_message_index is not None:
		return next_user_message_index
	for index in range(candidate_index, len(messages)):
		if not isinstance(messages[index], ToolResult):
			return index
	return len(messages)


def _next_user_message_index(messages: Sequence[TranscriptMessage], *, start: int) -> int | None:
	for index in range(start, len(messages)):
		if isinstance(messages[index], UserMessage):
			return index
	return None


# --- summarization ----------------------------------------------------------


def build_summary_prompt(
	compaction_plan: CompactionPlan,
	summary_instructions: str | None = None,
	*,
	max_summary_prompt_tokens: int | None = None,
	resolve_attachment: Callable[[str], bytes] | None = None,
) -> str:
	summary_prompt_template = (
		UPDATE_SUMMARIZATION_PROMPT if compaction_plan.previous_summary is not None else SUMMARIZATION_PROMPT
	)
	summary_instructions = (
		summary_instructions.strip() if summary_instructions and summary_instructions.strip() else None
	)
	if max_summary_prompt_tokens is None:
		return _render_summary_prompt(
			serialize_messages(
				compaction_plan.messages_to_summarize,
				resolve_attachment=resolve_attachment,
			),
			compaction_plan.previous_summary,
			summary_prompt_template,
			summary_instructions,
		)

	max_summary_prompt_chars = max(0, max_summary_prompt_tokens) * CHARS_PER_TOKEN
	fixed_summary_prompt = _render_summary_prompt(
		"",
		"" if compaction_plan.previous_summary is not None else None,
		summary_prompt_template,
		"" if summary_instructions else None,
	)
	if len(fixed_summary_prompt) > max_summary_prompt_chars:
		raise RuntimeError("model context window is too small for the compaction prompt")

	remaining_summary_prompt_chars = max_summary_prompt_chars - len(fixed_summary_prompt)
	bounded_summary_instructions: str | None = None
	if summary_instructions is not None:
		max_instruction_chars = min(
			MAX_SUMMARY_INSTRUCTION_CHARS,
			remaining_summary_prompt_chars,
		)
		bounded_summary_instructions = _fit_text(summary_instructions, max_instruction_chars)
		remaining_summary_prompt_chars -= len(bounded_summary_instructions)

	previous_summary = compaction_plan.previous_summary
	if previous_summary is not None:
		previous_summary = _fit_text(previous_summary, remaining_summary_prompt_chars)
		remaining_summary_prompt_chars -= len(previous_summary)
	serialized_conversation = serialize_messages(
		compaction_plan.messages_to_summarize,
		max_serialized_chars=remaining_summary_prompt_chars,
		resolve_attachment=resolve_attachment,
	)

	summary_prompt = _render_summary_prompt(
		serialized_conversation,
		previous_summary,
		summary_prompt_template,
		bounded_summary_instructions,
	)
	if len(summary_prompt) > max_summary_prompt_chars:
		raise RuntimeError("compaction prompt budgeting failed")
	return summary_prompt


def _render_summary_prompt(
	serialized_conversation: str,
	previous_summary: str | None,
	prompt_template: str,
	summary_instructions: str | None,
) -> str:
	prompt_prefix = f"<conversation>\n{serialized_conversation}\n</conversation>\n\n"
	if previous_summary is not None:
		prompt_prefix += f"<previous-summary>\n{previous_summary}\n</previous-summary>\n\n"
	if summary_instructions is not None:
		prompt_template = f"{prompt_template}\n\nAdditional focus: {summary_instructions}"
	return prompt_prefix + prompt_template


def serialize_messages(
	messages: Sequence[TranscriptMessage],
	*,
	max_serialized_chars: int | None = None,
	resolve_attachment: Callable[[str], bytes] | None = None,
) -> str:
	"""Serialize as text so the summarizer reads, not continues, the conversation.
	Tool payloads are clipped; `max_serialized_chars` drops old messages when necessary."""
	if not messages:
		return (
			_fit_text("(no new messages)", max_serialized_chars)
			if max_serialized_chars is not None
			else "(no new messages)"
		)
	message_blocks = [
		_serialize_message(message_number, message, resolve_attachment=resolve_attachment)
		for message_number, message in enumerate(messages, start=1)
	]
	serialized_messages = "\n".join(message_blocks)
	if max_serialized_chars is None or len(serialized_messages) <= max_serialized_chars:
		return serialized_messages

	omission_marker = "[... older messages omitted]\n"
	remaining_message_chars = max_serialized_chars - len(omission_marker)
	if remaining_message_chars <= 0:
		return _fit_text(_message_preview(messages[-1]), max_serialized_chars)

	retained_message_blocks: list[str] = []
	retained_message_chars = 0
	for message_block in reversed(message_blocks):
		separator_chars = 1 if retained_message_blocks else 0
		if retained_message_chars + separator_chars + len(message_block) > remaining_message_chars:
			if not retained_message_blocks:
				retained_message_blocks.append(_fit_text(message_block, remaining_message_chars))
			break
		retained_message_blocks.append(message_block)
		retained_message_chars += separator_chars + len(message_block)
	retained_message_blocks.reverse()
	return omission_marker + "\n".join(retained_message_blocks)


def _serialize_message(
	message_number: int,
	message: TranscriptMessage,
	*,
	resolve_attachment: Callable[[str], bytes] | None = None,
) -> str:
	lines: list[str] = []
	if isinstance(message, UserMessage):
		lines.append(f"<message index={message_number} role=user>")
		content = attachment_summary(
			message,
			resolve_attachment=resolve_attachment,
			include_text_contents=True,
		)
		if content:
			lines.append(content)
	elif isinstance(message, AssistantMessage):
		lines.append(f"<message index={message_number} role=assistant>")
		if message.thinking_text:
			lines.extend(("<thinking>", message.thinking_text, "</thinking>"))
		if message.text:
			lines.append(message.text)
		if message.tool_calls:
			lines.append("<tool-calls>")
			for call in message.tool_calls:
				serialized_arguments = _clip(
					json.dumps(call.arguments, default=str),
					MAX_TOOL_CONTENT_CHARS_IN_SUMMARY,
				)
				lines.append(f"- {call.name}: {serialized_arguments}")
			lines.append("</tool-calls>")
	else:
		error = str(message.is_error).lower()
		lines.append(f"<message index={message_number} role=tool_result name={message.name} error={error}>")
		if message.content:
			lines.append(_clip(message.content, MAX_TOOL_CONTENT_CHARS_IN_SUMMARY))
	lines.append("</message>")
	return "\n".join(lines)


def _clip(text: str, max_content_chars: int) -> str:
	"""Keep the beginning and mark the cut (pi's truncateForSummary)."""
	if len(text) <= max_content_chars:
		return text
	truncated_chars = len(text) - max_content_chars
	return f"{text[:max_content_chars]}\n[... {truncated_chars} more characters truncated]"


def _fit_text(text: str, max_result_chars: int) -> str:
	"""Fit text inside an exact character budget, including the truncation marker."""
	if max_result_chars <= 0:
		return ""
	if len(text) <= max_result_chars:
		return text
	truncation_marker = "\n[... truncated]"
	if len(truncation_marker) >= max_result_chars:
		return text[:max_result_chars]
	return text[: max_result_chars - len(truncation_marker)] + truncation_marker


def _message_preview(message: TranscriptMessage) -> str:
	if isinstance(message, UserMessage):
		return attachment_summary(message)
	if isinstance(message, AssistantMessage):
		return message.text or ", ".join(call.name for call in message.tool_calls)
	return message.content


# --- estimation (chars/4, deterministic and offline) -----------------------


def estimate_context_tokens(
	system_prompt: str,
	tool_schemas: Sequence[dict] | None,
	messages: Sequence[TranscriptMessage],
) -> int:
	"""A full estimate of one provider request: system prompt + tool schemas + messages."""
	estimated_context_tokens = estimate_text_tokens(system_prompt)
	for tool_schema in tool_schemas or ():
		estimated_context_tokens += TOOL_OVERHEAD_TOKENS + estimate_text_tokens(
			json.dumps(tool_schema, default=str)
		)
	return estimated_context_tokens + sum(estimate_message_tokens(message) for message in messages)


def estimate_message_tokens(message: TranscriptMessage) -> int:
	estimated_message_tokens = MESSAGE_OVERHEAD_TOKENS
	if isinstance(message, UserMessage):
		estimated_message_tokens += estimate_text_tokens(attachment_summary(message))
		for attachment in message.attachments:
			# Text bytes become prompt text at the provider boundary. Images use a
			# conservative fixed estimate because providers tokenize pixels differently.
			# A file sends only its note, counted above.
			if attachment.kind == "text":
				estimated_message_tokens += max(1, (attachment.size + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN)
			elif attachment.kind == "image":
				estimated_message_tokens += ESTIMATED_IMAGE_TOKENS
	elif isinstance(message, AssistantMessage):
		estimated_message_tokens += estimate_text_tokens(message.text)
		estimated_message_tokens += estimate_text_tokens(message.thinking_text)
		for tool_call in message.tool_calls:
			estimated_message_tokens += estimate_text_tokens(tool_call.name)
			estimated_message_tokens += estimate_text_tokens(json.dumps(tool_call.arguments, default=str))
	else:
		estimated_message_tokens += estimate_text_tokens(message.name)
		estimated_message_tokens += estimate_text_tokens(message.content)
		estimated_message_tokens += ESTIMATED_IMAGE_TOKENS * len(message.attachments)
	return estimated_message_tokens


def estimate_text_tokens(text: str) -> int:
	if not text:
		return 0
	return max(1, (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN)


__all__ = [
	"DEFAULT_CONTEXT_WINDOW_TOKENS",
	"KEEP_RECENT_TOKENS",
	"MAX_RESERVED_OUTPUT_TOKENS",
	"CompactionPlan",
	"build_summary_prompt",
	"calculate_compaction_input_limit",
	"calculate_reserved_output_tokens",
	"compact_events",
	"estimate_context_tokens",
	"estimate_message_tokens",
	"estimate_text_tokens",
	"plan_all",
	"plan_keep_recent",
	"serialize_messages",
	"summarize",
]
