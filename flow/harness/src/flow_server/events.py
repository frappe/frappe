"""The event protocol — the single contract between the loop, the log, and clients.

Two families of events:
  - durable: assigned a monotonic `seq` and persisted to the session log. These
    reconstruct the conversation on replay/restart.
  - live-only: transient token/tool deltas for a responsive UI. Never persisted;
    the durable log + replay heals any gap if a client misses them.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

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


class ToolCall(BaseModel):
	"""A tool invocation in the assistant's ordered content."""

	model_config = ConfigDict(extra="forbid")

	type: Literal["tool_call"] = "tool_call"
	id: str
	name: str
	arguments: dict
	# Set when the model emitted unparseable arguments; the agent feeds this back so it can
	# retry.
	error: str | None = None

	@property
	def args(self) -> dict:
		"""Compatibility view used by Flow's tool-dispatch API."""
		return self.arguments


class TextContent(BaseModel):
	model_config = ConfigDict(extra="forbid")

	type: Literal["text"] = "text"
	text: str
	text_signature: str | None = None


class ThinkingContent(BaseModel):
	model_config = ConfigDict(extra="forbid")

	type: Literal["thinking"] = "thinking"
	thinking: str
	thinking_signature: str | None = None
	redacted: bool = False


AssistantContent = Annotated[TextContent | ThinkingContent | ToolCall, Field(discriminator="type")]
StopReason = Literal["stop", "length", "tool_use", "error", "aborted"]


class _Event(BaseModel):
	model_config = ConfigDict(extra="forbid")

	seq: int | None = None  # assigned by the log when persisted
	durable: bool = Field(default=True, exclude=True)


# --- durable events -------------------------------------------------------


class RunStarted(_Event):
	type: Literal["run_started"] = "run_started"
	run_id: str


class UserMessage(_Event):
	type: Literal["user_message"] = "user_message"
	content: str


class AssistantMessage(_Event):
	"""Final provider response ordered by content blocks."""

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
		"""Allow concise Python constructor while keeping one serialized shape."""
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


TranscriptMessage = UserMessage | AssistantMessage | ToolResult


class Usage(_Event):
	type: Literal["usage"] = "usage"
	input_tokens: int = 0
	output_tokens: int = 0
	cost: float = 0.0


class PendingCall(BaseModel):
	id: str
	name: str
	args: dict
	prompt: str = ""  # human-facing approval prompt, resolved by the client


class ApprovalRequired(_Event):
	"""The model called one or more confirmation-gated tools; the run pauses here until
	a `resume` supplies a decision (Approve / Deny / free-text redirect) per call."""

	type: Literal["approval_required"] = "approval_required"
	calls: list[PendingCall] = Field(default_factory=list)


class RunEnded(_Event):
	type: Literal["run_ended"] = "run_ended"
	reason: Literal["done", "length", "max_turns", "budget", "aborted", "error", "paused"] = "done"


class RunError(_Event):
	type: Literal["run_error"] = "run_error"
	message: str
	kind: ProviderErrorKind | None = None
	retryable: bool | None = None
	status_code: int | None = None
	provider: str | None = None
	detail: str | None = None


# --- live-only events -----------------------------------------------------


class TextDelta(_Event):
	type: Literal["text_delta"] = "text_delta"
	text: str
	durable: bool = Field(default=False, exclude=True)


class ToolCallStarted(_Event):
	type: Literal["tool_call_started"] = "tool_call_started"
	id: str
	name: str
	durable: bool = Field(default=False, exclude=True)


class RetryScheduled(_Event):
	type: Literal["retry_scheduled"] = "retry_scheduled"
	attempt: int
	max_attempts: int
	delay_seconds: float
	kind: ProviderErrorKind
	durable: bool = Field(default=False, exclude=True)


class RetryStarted(_Event):
	type: Literal["retry_started"] = "retry_started"
	attempt: int
	durable: bool = Field(default=False, exclude=True)


class RetryExhausted(_Event):
	type: Literal["retry_exhausted"] = "retry_exhausted"
	attempts: int
	kind: ProviderErrorKind
	durable: bool = Field(default=False, exclude=True)


AnyEvent = (
	RunStarted
	| UserMessage
	| AssistantMessage
	| ToolResult
	| Usage
	| ApprovalRequired
	| RunEnded
	| RunError
	| TextDelta
	| ToolCallStarted
	| RetryScheduled
	| RetryStarted
	| RetryExhausted
)

Event = Annotated[AnyEvent, Field(discriminator="type")]

_ADAPTER: TypeAdapter[AnyEvent] = TypeAdapter(Event)


def parse_event(data: dict) -> AnyEvent:
	"""Validate and rebuild a typed event from its durable wire representation."""
	return _ADAPTER.validate_python(data)
