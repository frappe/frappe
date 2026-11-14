"""The transcript view: one widget per durable entry in a `VerticalScroll`, with the
streamed preview always mounted last. Anchored to the bottom — textual's `anchor()`
keeps following new output unless the user scrolls up.

A `ToolResult` entry does not get its own widget: it merges into the `ToolCallView`
of the call that produced it, so a call and its result read as one line. The view
keeps a call-id registry to find that widget, and prunes it on rewind.
"""

from __future__ import annotations

from textual.containers import VerticalScroll

from flow_harness.events import ToolResult, TranscriptMessage
from flow_tui.client.state import PartialPart
from flow_tui.widgets.messages import EntryView, PartialAssistantView, ThinkingBlock, ToolCallView


class ConversationView(VerticalScroll, can_focus=False):
	def __init__(self, **kwargs) -> None:
		super().__init__(**kwargs)
		self._partial: PartialAssistantView | None = None
		self._partial_parts: list[PartialPart] = []
		self._tool_calls: dict[str, ToolCallView] = {}
		self.show_thinking = False
		self.expand_tools = False
		self.running = False

	def on_mount(self) -> None:
		self.anchor()

	def add_entry(self, entry: TranscriptMessage, *, steered: bool = False) -> None:
		if isinstance(entry, ToolResult):
			widget = self._tool_calls.get(entry.tool_call_id)
			if widget is not None:
				widget.set_result(entry)
				return
		view = EntryView(
			entry,
			steered=steered,
			show_thinking=self.show_thinking,
			expand_tools=self.expand_tools,
			running=self.running,
		)
		self.mount(view, before=self._partial)
		self._tool_calls.update(view.tool_calls)

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
		for call_id, widget in list(self._tool_calls.items()):
			if widget.entry_seq is None or widget.entry_seq > target_seq:
				del self._tool_calls[call_id]
			elif widget.result_seq is not None and widget.result_seq > target_seq:
				widget.clear_result()

	def set_running(self, running: bool) -> None:
		"""Keep resultless tool calls honest: spin while the run is live, settle to a
		quiet dot when it is not."""
		if running == self.running:
			return
		self.running = running
		for widget in self.query(ToolCallView):
			widget.set_running(running)

	def set_show_thinking(self, value: bool) -> None:
		"""Flip every thinking block, existing and future, and the live preview."""
		self.show_thinking = value
		for block in self.query(ThinkingBlock):
			block.collapsed = not value
		if self._partial is not None:
			self._partial.update_parts(self._partial_parts, show_thinking=value)

	def set_expand_tools(self, value: bool) -> None:
		"""Flip every tool result body, existing and future, between preview and full."""
		self.expand_tools = value
		for widget in self.query(ToolCallView):
			widget.expanded = value
