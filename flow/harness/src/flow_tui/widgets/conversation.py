"""The transcript view: one widget per durable entry in a `VerticalScroll`, with the
streamed preview always mounted last. Anchored to the bottom — textual's `anchor()`
keeps following new output unless the user scrolls up."""

from __future__ import annotations

from textual.containers import VerticalScroll

from flow.events import TranscriptMessage
from flow_tui.client.state import PartialPart
from flow_tui.widgets.messages import EntryView, PartialAssistantView


class ConversationView(VerticalScroll, can_focus=False):
	def __init__(self, **kwargs) -> None:
		super().__init__(**kwargs)
		self._partial: PartialAssistantView | None = None

	def on_mount(self) -> None:
		self.anchor()

	def add_entry(self, entry: TranscriptMessage, *, steered: bool = False) -> None:
		self.mount(EntryView(entry, steered=steered), before=self._partial)

	def replace_partial(self, entry: TranscriptMessage) -> None:
		self.clear_partial()
		self.add_entry(entry)

	def show_partial(self, parts: list[PartialPart]) -> None:
		if self._partial is None:
			self._partial = PartialAssistantView(classes="partial")
			self.mount(self._partial)
		self._partial.update_parts(parts)

	def clear_partial(self) -> None:
		if self._partial is not None:
			self._partial.remove()
			self._partial = None

	def truncate(self, target_seq: int) -> None:
		for view in self.query(EntryView):
			if view.seq is None or view.seq > target_seq:
				view.remove()
