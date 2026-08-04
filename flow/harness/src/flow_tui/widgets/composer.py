"""The message input: a `TextArea` where Enter submits, ctrl+j inserts a newline, and
alt+enter asks the app to queue the message for after the current run. Lines that
start with `/` are commands, never conversation — they dispatch immediately.

`ctrl+x` arms a short-lived chord; `ctrl+e` while armed asks the app to open the
draft in the external editor."""

from __future__ import annotations

from textual import events
from textual.message import Message
from textual.timer import Timer
from textual.widgets import TextArea

CHORD_TIMEOUT = 1.5


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

	class EditRequested(Message):
		pass

	_chord_timer: Timer | None = None

	@property
	def chord_armed(self) -> bool:
		return self._chord_timer is not None

	def _arm_chord(self) -> None:
		self._disarm_chord()
		self._chord_timer = self.set_timer(CHORD_TIMEOUT, self._disarm_chord)

	def _disarm_chord(self) -> None:
		if self._chord_timer is not None:
			self._chord_timer.stop()
			self._chord_timer = None

	async def _on_key(self, event: events.Key) -> None:
		if self.chord_armed:
			self._disarm_chord()
			if event.key == "ctrl+e":
				event.stop()
				event.prevent_default()
				self.post_message(self.EditRequested())
				return
		if event.key == "ctrl+x":
			event.stop()
			event.prevent_default()
			self._arm_chord()
			return
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
