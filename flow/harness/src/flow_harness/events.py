"""Events shared by the loop, log, and clients.

Durable events are stored. Active previews are kept in memory for reconnects.
"""

from __future__ import annotations

from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, TypeAdapter, model_validator

ReasoningEffort = Literal["off", "minimal", "low", "medium", "high", "xhigh", "max"]

ProviderErrorKind = Literal[
	"rate_limit",
	"overloaded",
	"timeout",
	"auth",
	"context_overflow",
	"invalid_request",
	"transport",
	"unknown",
]


# --- assistant content blocks ---------------------------------------------


class DisplaySegment(BaseModel):
	"""One piece of rendered tool display text. ``arg`` names the argument a value
	segment came from; template text otherwise."""

	model_config = ConfigDict(extra="forbid")

	text: str
	arg: str | None = None


def _legacy_display(value: object) -> object:
	# Early builds rendered display as one flat string; read it as a single segment.
	return [{"text": value}] if isinstance(value, str) else value


ToolDisplay = Annotated[list[DisplaySegment] | None, BeforeValidator(_legacy_display)]


class ToolCall(BaseModel):
	"""A tool invocation in the assistant's ordered content."""

	model_config = ConfigDict(extra="forbid")

	type: Literal["tool_call"] = "tool_call"
	id: str
	name: str
	arguments: dict
	# Rendered user-facing activity text declared by the tool. This is presentation
	# metadata only and is never included in provider tool-call arguments.
	display: ToolDisplay = None
	# Set when the model emitted unparseable arguments; fed back so it can retry.
	error: str | None = None
	# Opaque provider round-trip data (e.g. a Responses item id). Never shown to the
	# model or a UI; only the provider that wrote it reads it.
	provider_state: dict | None = None

	@property
	def args(self) -> dict:
		"""Compatibility view used by Flow's tool-dispatch API."""
		return self.arguments


class TextContent(BaseModel):
	model_config = ConfigDict(extra="forbid")

	type: Literal["text"] = "text"
	text: str
	provider_state: dict | None = None


class ThinkingContent(BaseModel):
	model_config = ConfigDict(extra="forbid")

	type: Literal["thinking"] = "thinking"
	thinking: str
	thinking_signature: str | None = None
	redacted: bool = False
	provider_state: dict | None = None


AssistantContent = Annotated[TextContent | ThinkingContent | ToolCall, Field(discriminator="type")]


class AttachmentContent(BaseModel):
	"""Immutable metadata for bytes stored outside the event log. A `file` reaches the model as its `path`."""

	model_config = ConfigDict(extra="forbid")

	type: Literal["attachment"] = "attachment"
	id: str
	name: str
	mime_type: str
	size: int = Field(ge=0)
	kind: Literal["text", "image", "file"]
	width: int | None = Field(default=None, gt=0)
	height: int | None = Field(default=None, gt=0)
	path: str | None = None


UserContent = Annotated[TextContent | AttachmentContent, Field(discriminator="type")]

StopReason = Literal["stop", "length", "tool_use", "error", "aborted"]


class _Event(BaseModel):
	model_config = ConfigDict(extra="forbid")

	durable: ClassVar[bool] = True
	seq: int | None = None  # assigned by the log when persisted
	parent_seq: int | None = None  # the entry this one follows; 0 at the root
	ts: float | None = None  # unix seconds, stamped by the log when persisted
	subagent_id: str | None = None  # the sub-agent run this event belongs to; None for the session's own


# --- durable events -------------------------------------------------------


class RunStarted(_Event):
	type: Literal["run_started"] = "run_started"
	run_id: str


class UserMessage(_Event):
	type: Literal["user_message"] = "user_message"
	content: str | list[UserContent]

	@property
	def text(self) -> str:
		if isinstance(self.content, str):
			return self.content
		return "".join(block.text for block in self.content if isinstance(block, TextContent))

	@property
	def attachments(self) -> tuple[AttachmentContent, ...]:
		if isinstance(self.content, str):
			return ()
		return tuple(block for block in self.content if isinstance(block, AttachmentContent))


class AssistantMessage(_Event):
	"""Final provider response, ordered by content blocks."""

	type: Literal["assistant_message"] = "assistant_message"
	content: list[AssistantContent] = Field(default_factory=list)
	api: str = "unknown"
	provider: str = "unknown"
	model: str = "unknown"
	response_model: str | None = None
	response_id: str | None = None
	stop_reason: StopReason = "stop"
	error_message: str | None = None

	@model_validator(mode="before")
	@classmethod
	def _normalize_content_string(cls, value: object) -> object:
		"""Allow the concise `content="text"` constructor while keeping one wire shape."""
		if not isinstance(value, dict):
			return value
		data = dict(value)
		content = data.get("content")
		if isinstance(content, str):
			data["content"] = [TextContent(text=content)] if content else []
		return data

	@property
	def text(self) -> str:
		return "".join(block.text for block in self.content if isinstance(block, TextContent))

	@property
	def thinking_text(self) -> str:
		return "".join(block.thinking for block in self.content if isinstance(block, ThinkingContent))

	@property
	def tool_calls(self) -> tuple[ToolCall, ...]:
		return tuple(block for block in self.content if isinstance(block, ToolCall))


class ToolResult(_Event):
	type: Literal["tool_result"] = "tool_result"
	tool_call_id: str
	name: str
	content: str  # the text the model sees
	is_error: bool = False
	# structured render metadata (diff, truncation, exit code, ...); never sent to the model
	details: dict = Field(default_factory=dict)
	# images the tool produced; metadata only, the bytes live beside the log
	attachments: list[AttachmentContent] = Field(default_factory=list)


TranscriptMessage = UserMessage | AssistantMessage | ToolResult


class Usage(_Event):
	type: Literal["usage"] = "usage"
	input_tokens: int = 0
	output_tokens: int = 0
	cache_read_tokens: int = 0
	cache_write_tokens: int = 0
	cost: float = 0.0
	context_window: int | None = None
	# the summarizer's own call: count its tokens as spend, not as the context size
	standalone: bool = False


class PendingCall(BaseModel):
	id: str
	name: str
	args: dict
	prompt: str = ""  # human-facing approval prompt, resolved by the client


class ApprovalRequired(_Event):
	"""The model called confirmation-gated tools; the run pauses here until a `resume`
	supplies a decision (Approve / Deny / free-text redirect) per call."""

	type: Literal["approval_required"] = "approval_required"
	calls: list[PendingCall] = Field(default_factory=list)


RunEndReason = Literal["done", "length", "max_turns", "budget", "aborted", "error", "paused", "denied"]


class RunEnded(_Event):
	type: Literal["run_ended"] = "run_ended"
	reason: RunEndReason = "done"


class Rewind(_Event):
	"""Moves the leaf back to an earlier entry; later events branch from there."""

	type: Literal["rewind"] = "rewind"
	target_seq: int


class ModelChanged(_Event):
	"""Selects the model (and credential) for runs from here on; per-branch, so a rewind
	to before this entry restores the previous selection."""

	type: Literal["model_changed"] = "model_changed"
	model: str
	credential_id: str | None = None  # None = inferred from the model prefix
	reasoning_effort: ReasoningEffort | None = None  # None = provider default


class RunError(_Event):
	type: Literal["run_error"] = "run_error"
	message: str
	kind: ProviderErrorKind | None = None
	retryable: bool | None = None
	status_code: int | None = None
	provider: str | None = None
	detail: str | None = None


CompactionReason = Literal["manual", "threshold", "overflow"]


class Compaction(_Event):
	"""A summary of transcript messages up to `compact_up_to_seq`; replay folds it
	while the original rows remain in the log."""

	type: Literal["compaction"] = "compaction"
	reason: CompactionReason
	summary: str
	compact_up_to_seq: int


# --- live-only events -----------------------------------------------------


class TextDelta(_Event):
	durable: ClassVar[bool] = False
	type: Literal["text_delta"] = "text_delta"
	text: str


class ThinkingDelta(_Event):
	durable: ClassVar[bool] = False
	type: Literal["thinking_delta"] = "thinking_delta"
	thinking: str


class ToolCallStarted(_Event):
	durable: ClassVar[bool] = False
	type: Literal["tool_call_started"] = "tool_call_started"
	id: str
	name: str


class ToolCallDisplayReady(_Event):
	"""Small, presentation-safe metadata parsed from a streamed tool call."""

	durable: ClassVar[bool] = False
	type: Literal["tool_call_display_ready"] = "tool_call_display_ready"
	id: str
	name: str
	arguments: dict[str, str]
	display: ToolDisplay = None


class Retry(_Event):
	"""Provider retry progress: an attempt was scheduled, started, or given up on."""

	durable: ClassVar[bool] = False
	type: Literal["retry"] = "retry"
	status: Literal["scheduled", "started", "exhausted"]
	attempt: int
	max_attempts: int | None = None
	delay_seconds: float | None = None
	kind: ProviderErrorKind | None = None


class CompactionStarted(_Event):
	"""A summarization call is in flight; `CompactionEnded` closes the pair."""

	durable: ClassVar[bool] = False
	type: Literal["compaction_started"] = "compaction_started"
	reason: CompactionReason


class CompactionEnded(_Event):
	durable: ClassVar[bool] = False
	type: Literal["compaction_ended"] = "compaction_ended"
	reason: CompactionReason
	error_message: str | None = None


class PreviewReplayStarted(_Event):
	"""Starts a full replay of the active preview."""

	durable: ClassVar[bool] = False
	type: Literal["preview_replay_started"] = "preview_replay_started"


class TitleChanged(_Event):
	"""The session's generated display title landed; it lives in session meta, not the
	log, so late subscribers read it from the session detail instead of replay."""

	durable: ClassVar[bool] = False
	type: Literal["title_changed"] = "title_changed"
	title: str


AnyEvent = (
	RunStarted
	| UserMessage
	| AssistantMessage
	| ToolResult
	| Usage
	| ApprovalRequired
	| Rewind
	| ModelChanged
	| Compaction
	| RunEnded
	| RunError
	| TextDelta
	| ThinkingDelta
	| ToolCallStarted
	| ToolCallDisplayReady
	| Retry
	| CompactionStarted
	| CompactionEnded
	| PreviewReplayStarted
	| TitleChanged
)

Event = Annotated[AnyEvent, Field(discriminator="type")]

_ADAPTER: TypeAdapter[AnyEvent] = TypeAdapter(Event)


def parse_event(data: dict[str, Any]) -> AnyEvent:
	"""Validate and rebuild a typed event from its durable wire representation."""
	return _ADAPTER.validate_python(data)
