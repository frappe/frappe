"""The message input: a `TextArea` where Enter submits, ctrl+j inserts a newline, and
alt+enter asks the app to queue the message for after the current run. Lines that
start with `/` are commands, never conversation — they dispatch immediately."""

from __future__ import annotations

from textual import events
from textual.message import Message
from textual.widgets import TextArea


class Composer(TextArea):
	class Submitted(Message):
		def __init__(self, text: str, *, queue: bool = False) -> None:
			self.text = text
			self.queue = queue
			super().__init__()

	class CommandSubmitted(Message):
		def __init__(self, line: str) -> None:
			self.line = line
			super().__init__()

	async def _on_key(self, event: events.Key) -> None:
		if event.key in ("enter", "alt+enter"):
			event.stop()
			event.prevent_default()
			text = self.text.strip()
			if text.startswith("/"):
				self.post_message(self.CommandSubmitted(text))
				self.clear()
			elif text:
				self.post_message(self.Submitted(text, queue=event.key == "alt+enter"))
				self.clear()
			return
		if event.key == "ctrl+j":
			event.stop()
			event.prevent_default()
			self.insert("\n")
			return
		await super()._on_key(event)
