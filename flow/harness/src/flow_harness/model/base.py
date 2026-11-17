"""The provider contract: one `Model.run` call is one streamed model turn.

An adapter yields `TextDelta` / `ThinkingDelta` / `ToolCallStarted` / `ToolCallDisplayReady`
while streaming, then always terminates with an `AssistantMessage` followed by a `Usage`.
Everything that can go wrong with a provider is owned by this package too, so the agent
loop never has to care:

  - failures are raised as a typed `ProviderError` (see `errors.py`);
  - transient failures are retried inside the stream by `retry.run_with_retries`, which
    emits `Retry` progress events between attempts — a retry may only happen before the terminal
    `AssistantMessage` is out, since that is the moment the turn becomes durable;
  - cancellation ends the turn gracefully with an `AssistantMessage(stop_reason=
    "aborted")`, so an aborted run still leaves a well-formed transcript.
"""

from __future__ import annotations

import abc
import asyncio
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from flow_harness.events import AnyEvent, AssistantMessage, TranscriptMessage


@dataclass(slots=True)
class ModelRequest:
	"""Provider-neutral input for one model turn.

	``cancellation`` is owned by the session. Adapters race their transport against it
	so a hung provider cannot hold a run open. ``params`` are provider-shaped request
	params for this turn, such as the reasoning effort, merged over the client's own.
	"""

	messages: list[TranscriptMessage]
	tools: list[dict[str, Any]] | None = None
	system_prompt: str = "You are a helpful assistant."
	stream: bool = True
	cancellation: asyncio.Event | None = None
	max_output_tokens: int | None = None
	resolve_attachment: Callable[[str], bytes] | None = None
	tool_display_templates: Mapping[str, str] = field(default_factory=dict)
	params: Mapping[str, Any] | None = None


class Model(abc.ABC):
	name: str
	api: str = "unknown"
	provider: str = "unknown"
	model: str = "unknown"

	@property
	def supports_images(self) -> bool | None:
		"""Whether this serving surface accepts image input; None when unknown."""
		return None

	@property
	def context_window(self) -> int | None:
		"""Tokens of context the model accepts; None means unknown."""
		return None

	@property
	def max_output_tokens(self) -> int | None:
		"""Largest output the model accepts; None means the adapter does not know."""
		return None

	@property
	def auto_compact_threshold_tokens(self) -> int | None:
		"""Provider-recommended input size for automatic compaction, if known."""
		return None

	async def load_model_limits(self, cancellation: asyncio.Event | None = None) -> None:
		"""Load serving-surface-specific limits when a provider exposes them."""
		return None

	@abc.abstractmethod
	def run(self, request: ModelRequest) -> AsyncIterator[AnyEvent]:
		"""Run one model turn over the provider-neutral transcript, yielding typed events."""

	def aborted_message(self) -> AssistantMessage:
		"""The graceful terminal for a cancelled turn."""
		return AssistantMessage(api=self.api, provider=self.provider, model=self.model, stop_reason="aborted")
