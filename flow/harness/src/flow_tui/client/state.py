"""ConversationState — a pure reducer from the event stream to what a client renders.

`apply` folds one event at a time and returns typed change notices, so a TUI can
update widgets incrementally instead of re-rendering the whole transcript. No I/O
happens here; seeding and event delivery are the controller's job.

The rules mirror the wire contract:
  - live deltas accumulate into `partial`, the streamed preview at the tail; the
    durable `assistant_message` supersedes it (`EntryReplaced`);
  - `retry(status="started")` discards the preview from the failed attempt;
  - `approval_required` pends until matching tool results, a `run_started`, or a
    non-paused `run_ended` settle it;
  - `rewind` truncates the active path and refolds model/effort from what is left,
    falling back to the seeded session config;
  - a sub-agent's rows (tagged `subagent_id`) add its messages and results to the
    transcript and its usage to the totals; its previews and pauses stay its own.

Replaying history through `apply` (from `GET /entries?path=active`) and folding the
live stream use the same code path, so a reattached client and a live one agree.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from flow_harness.events import (
	AnyEvent,
	ApprovalRequired,
	AssistantMessage,
	Compaction,
	DisplaySegment,
	ModelChanged,
	PendingCall,
	PreviewReplayStarted,
	ReasoningEffort,
	Retry,
	Rewind,
	RunEnded,
	RunError,
	RunStarted,
	TextDelta,
	ThinkingDelta,
	ToolCallDisplayReady,
	ToolCallStarted,
	ToolResult,
	TranscriptMessage,
	Usage,
	UserMessage,
)

# --- change notices --------------------------------------------------------


@dataclass(frozen=True)
class EntryAdded:
	"""A durable message was appended to the transcript."""

	entry: TranscriptMessage


@dataclass(frozen=True)
class EntryReplaced:
	"""The streamed preview at the tail became this durable message; swap, don't append."""

	entry: AssistantMessage


@dataclass(frozen=True)
class EntriesTruncated:
	"""A rewind cut the transcript back to `target_seq`; drop the widgets past it."""

	target_seq: int


@dataclass(frozen=True)
class StreamDelta:
	"""The streamed preview grew; `state.partial` holds the accumulated parts."""

	event: TextDelta | ThinkingDelta | ToolCallStarted | ToolCallDisplayReady


@dataclass(frozen=True)
class PartialCleared:
	"""The streamed preview was discarded without a durable replacement."""


@dataclass(frozen=True)
class ApprovalChanged:
	"""`state.pending_approval` was set, narrowed, or cleared."""


@dataclass(frozen=True)
class StatusChanged:
	"""Running/model/effort/usage/error/retry changed; re-render the status bar."""


Change = (
	EntryAdded
	| EntryReplaced
	| EntriesTruncated
	| StreamDelta
	| PartialCleared
	| ApprovalChanged
	| StatusChanged
)


# --- streamed preview parts ------------------------------------------------


@dataclass
class PartialText:
	text: str = ""


@dataclass
class PartialThinking:
	thinking: str = ""


@dataclass(frozen=True)
class PartialToolCall:
	id: str
	name: str
	arguments: dict[str, str] | None = None
	display: list[DisplaySegment] | None = None


PartialPart = PartialText | PartialThinking | PartialToolCall


@dataclass(frozen=True)
class PendingApproval:
	"""The approval batch a paused run waits on: its seq and the undecided calls."""

	seq: int | None
	calls: tuple[PendingCall, ...]


class ConversationState:
	def __init__(self) -> None:
		self.entries: list[TranscriptMessage] = []
		self.partial: list[PartialPart] = []
		self.pending_approval: PendingApproval | None = None
		self.running: bool = False
		self.cwd: str | None = None
		self.model: str | None = None
		self.credential_id: str | None = None
		self.reasoning_effort: ReasoningEffort | None = None
		self.input_tokens: int = 0
		self.output_tokens: int = 0
		self.cache_read_tokens: int = 0
		self.cache_write_tokens: int = 0
		self.context_tokens: int = 0
		self.context_window: int | None = None
		self.cost: float = 0.0
		self.last_error: RunError | None = None
		self.retry: Retry | None = None
		self.latest_seq: int = 0
		# the session-config baseline a rewind refolds back to when no model_changed remains
		self._base_model: str | None = None
		self._base_credential_id: str | None = None
		self._base_effort: ReasoningEffort | None = None
		self._model_history: list[ModelChanged] = []

	def seed(self, info: dict) -> None:
		"""Take the baseline from `GET /sessions/{sid}`.

		The config values anchor model refolds; the folded values cover clients that
		attach without replaying history. A subsequent replay through `apply` refolds
		to the same place, so seeding then replaying is safe.
		"""
		config = info.get("config") or {}
		self.cwd = config.get("cwd")
		self._base_model = config.get("model")
		self._base_credential_id = config.get("credential_id")
		self._base_effort = config.get("reasoning_effort")
		self.model = info.get("model", self._base_model)
		self.credential_id = info.get("credential_id", self._base_credential_id)
		self.reasoning_effort = info.get("reasoning_effort", self._base_effort)
		self.running = bool(info.get("running", False))
		self.latest_seq = int(info.get("latest_seq", 0))

	def apply(self, event: AnyEvent) -> list[Change]:
		"""Fold one event; return what a renderer must do about it."""
		if event.durable and event.seq is not None:
			self.latest_seq = max(self.latest_seq, event.seq)
		if event.subagent_id is not None:
			return self._apply_subagent(event)

		if isinstance(event, UserMessage):
			# arrives mid-run when steering; the preview keeps streaming, so keep it
			self.entries.append(event)
			return [EntryAdded(event)]

		if isinstance(event, AssistantMessage):
			had_partial = bool(self.partial)
			self.partial = []
			self.entries.append(event)
			changes: list[Change] = [EntryReplaced(event) if had_partial else EntryAdded(event)]
			if self.retry is not None:  # this attempt succeeded
				self.retry = None
				changes.append(StatusChanged())
			return changes

		if isinstance(event, ToolResult):
			self.entries.append(event)
			changes = [EntryAdded(event)]
			if self._settle_approval(event.tool_call_id):
				changes.append(ApprovalChanged())
			return changes

		if isinstance(event, ApprovalRequired):
			self.pending_approval = PendingApproval(seq=event.seq, calls=tuple(event.calls))
			return [ApprovalChanged()]

		if isinstance(event, RunStarted):
			changes = []
			if self.pending_approval is not None:
				self.pending_approval = None
				changes.append(ApprovalChanged())
			self.running = True
			self.last_error = None
			self.retry = None
			changes.append(StatusChanged())
			return changes

		if isinstance(event, RunEnded):
			changes = []
			if self.partial:
				self.partial = []
				changes.append(PartialCleared())
			# a pause outlives its run: `resume` may arrive much later
			if event.reason != "paused" and self.pending_approval is not None:
				self.pending_approval = None
				changes.append(ApprovalChanged())
			self.running = False
			self.retry = None
			changes.append(StatusChanged())
			return changes

		if isinstance(event, Rewind):
			return self._rewind(event.target_seq)

		if isinstance(event, ModelChanged):
			self._model_history.append(event)
			self._fold_model()
			self.context_tokens = 0
			self.context_window = None
			return [StatusChanged()]

		if isinstance(event, Compaction):
			self.context_tokens = 0
			return [StatusChanged()]

		if isinstance(event, RunError):
			self.last_error = event
			return [StatusChanged()]

		if isinstance(event, Usage):
			self.input_tokens += event.input_tokens
			self.output_tokens += event.output_tokens
			self.cache_read_tokens += event.cache_read_tokens
			self.cache_write_tokens += event.cache_write_tokens
			if not event.standalone:
				self.context_tokens = event.input_tokens + event.output_tokens
			if event.context_window is not None:
				self.context_window = event.context_window
			self.cost += event.cost
			return [StatusChanged()]

		if isinstance(event, PreviewReplayStarted):
			changes = []
			if self.partial:
				self.partial = []
				changes.append(PartialCleared())
			if self.retry is not None:
				self.retry = None
				changes.append(StatusChanged())
			return changes

		if isinstance(event, TextDelta):
			tail = self.partial[-1] if self.partial else None
			if isinstance(tail, PartialText):
				tail.text += event.text
			else:
				self.partial.append(PartialText(event.text))
			return [StreamDelta(event)]

		if isinstance(event, ThinkingDelta):
			tail = self.partial[-1] if self.partial else None
			if isinstance(tail, PartialThinking):
				tail.thinking += event.thinking
			else:
				self.partial.append(PartialThinking(event.thinking))
			return [StreamDelta(event)]

		if isinstance(event, ToolCallStarted):
			self.partial.append(PartialToolCall(id=event.id, name=event.name))
			return [StreamDelta(event)]

		if isinstance(event, ToolCallDisplayReady):
			ready = PartialToolCall(
				id=event.id,
				name=event.name,
				arguments=event.arguments,
				display=event.display,
			)
			for index in range(len(self.partial) - 1, -1, -1):
				part = self.partial[index]
				if isinstance(part, PartialToolCall) and part.id == event.id:
					self.partial[index] = ready
					break
			else:
				self.partial.append(ready)
			return [StreamDelta(event)]

		if isinstance(event, Retry):
			changes = []
			if event.status == "started" and self.partial:
				# the new attempt restreams from scratch; the old preview is dead
				self.partial = []
				changes.append(PartialCleared())
			self.retry = event
			changes.append(StatusChanged())
			return changes

		return []

	# --- internals --------------------------------------------------------

	def _apply_subagent(self, event: AnyEvent) -> list[Change]:
		if isinstance(event, (AssistantMessage, ToolResult)):
			self.entries.append(event)
			return [EntryAdded(event)]
		if isinstance(event, Usage):
			self.input_tokens += event.input_tokens
			self.output_tokens += event.output_tokens
			self.cache_read_tokens += event.cache_read_tokens
			self.cache_write_tokens += event.cache_write_tokens
			self.cost += event.cost
			return [StatusChanged()]
		return []

	def _settle_approval(self, call_id: str) -> bool:
		pending = self.pending_approval
		if pending is None or all(call.id != call_id for call in pending.calls):
			return False
		remaining = tuple(call for call in pending.calls if call.id != call_id)
		self.pending_approval = replace(pending, calls=remaining) if remaining else None
		return True

	def _rewind(self, target_seq: int) -> list[Change]:
		changes: list[Change] = []
		if self.partial:
			self.partial = []
			changes.append(PartialCleared())
		if self.pending_approval is not None:  # the server refuses to rewind over one, but be safe
			self.pending_approval = None
			changes.append(ApprovalChanged())
		self.entries = [entry for entry in self.entries if entry.seq is not None and entry.seq <= target_seq]
		self._model_history = [
			change for change in self._model_history if change.seq is not None and change.seq <= target_seq
		]
		self._fold_model()
		self.context_tokens = 0
		self.context_window = None
		changes.append(EntriesTruncated(target_seq))
		changes.append(StatusChanged())
		return changes

	def _fold_model(self) -> None:
		if self._model_history:
			latest = self._model_history[-1]
			self.model = latest.model
			self.credential_id = latest.credential_id
			self.reasoning_effort = latest.reasoning_effort
		else:
			self.model = self._base_model
			self.credential_id = self._base_credential_id
			self.reasoning_effort = self._base_effort
