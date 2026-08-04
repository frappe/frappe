"""The transcript view: one widget per durable entry in a `VerticalScroll`, with the
streamed preview always mounted last. Anchored to the bottom — textual's `anchor()`
keeps following new output unless the user scrolls up."""

from __future__ import annotations

from textual.containers import VerticalScroll

from flow.events import TranscriptMessage
from flow_tui.client.state import PartialPart
from flow_tui.widgets.messages import EntryView, PartialAssistantView, ThinkingBlock


class ConversationView(VerticalScroll, can_focus=False):
	def __init__(self, **kwargs) -> None:
		super().__init__(**kwargs)
		self._partial: PartialAssistantView | None = None
		self._partial_parts: list[PartialPart] = []
		self.show_thinking = False

	def on_mount(self) -> None:
		self.anchor()

	def add_entry(self, entry: TranscriptMessage, *, steered: bool = False) -> None:
		view = EntryView(entry, steered=steered, show_thinking=self.show_thinking)
		self.mount(view, before=self._partial)

	def replace_partial(self, entry: TranscriptMessage) -> None:
		self.clear_partial()
		self.add_entry(entry)

	def show_partial(self, parts: list[PartialPart]) -> None:
		self._partial_parts = parts
		if self._partial is None:
			self._partial = PartialAssistantView(classes="partial")
			self.mount(self._partial)
		self._partial.update_parts(parts, show_thinking=self.show_thinking)

	def clear_partial(self) -> None:
		self._partial_parts = []
		if self._partial is not None:
			self._partial.remove()
			self._partial = None

	def truncate(self, target_seq: int) -> None:
		for view in self.query(EntryView):
			if view.seq is None or view.seq > target_seq:
				view.remove()

	def set_show_thinking(self, value: bool) -> None:
		"""Flip every thinking block, existing and future, and the live preview."""
		self.show_thinking = value
		for block in self.query(ThinkingBlock):
			block.collapsed = not value
		if self._partial is not None:
			self._partial.update_parts(self._partial_parts, show_thinking=value)
