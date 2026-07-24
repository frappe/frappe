"""The event protocol — the single contract between the loop, the log, and clients.

Two families of events:
  - durable: assigned a monotonic `seq` and persisted to the session log. These
    reconstruct the conversation on replay/restart.
  - live-only: transient token/tool deltas for a responsive UI. Never persisted;
    the durable log + replay heals any gap if a client misses them.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
	id: str
	name: str
	args: dict
	# Set when the model emitted unparseable arguments; the agent feeds this back so it can
	# retry.
	error: str | None = None


class _Event(BaseModel):
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
	"""Final assembled assistant turn (text + any tool calls)."""

	type: Literal["assistant_message"] = "assistant_message"
	text: str = ""
	tool_calls: list[ToolCall] = Field(default_factory=list)
	# Opaque provider continuation state (for example encrypted Codex reasoning).
	# Durable so a tool turn can continue after reconnect/restart.
	provider_data: dict = Field(default_factory=dict)


class ToolResult(_Event):
	type: Literal["tool_result"] = "tool_result"
	tool_call_id: str
	name: str
	content: str  # the text the model sees
	is_error: bool = False
	# structured render metadata (diff, truncation, exit code, ...); never sent to the model
	details: dict = Field(default_factory=dict)


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
	reason: Literal["done", "max_turns", "budget", "aborted", "error", "paused"] = "done"


class RunError(_Event):
	type: Literal["run_error"] = "run_error"
	message: str


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


Event = Annotated[
	RunStarted
	| UserMessage
	| AssistantMessage
	| ToolResult
	| Usage
	| ApprovalRequired
	| RunEnded
	| RunError
	| TextDelta
	| ToolCallStarted,
	Field(discriminator="type"),
]

_TYPES = {
	"run_started": RunStarted,
	"user_message": UserMessage,
	"assistant_message": AssistantMessage,
	"tool_result": ToolResult,
	"usage": Usage,
	"approval_required": ApprovalRequired,
	"run_ended": RunEnded,
	"run_error": RunError,
	"text_delta": TextDelta,
	"tool_call_started": ToolCallStarted,
}


def parse_event(data: dict) -> _Event:
	"""Rebuild a typed event from a persisted/log dict."""
	return _TYPES[data["type"]].model_validate(data)
