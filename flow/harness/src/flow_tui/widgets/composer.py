"""The message input: a `TextArea` where Enter submits, ctrl+j inserts a newline, and
alt+enter asks the app to queue the message for after the current run. Local slash
commands dispatch immediately; `/skill:` directives are submitted prompts.

Up and down browse submitted prompts. `ctrl+x` arms a short-lived chord; `ctrl+e`
while armed asks the app to open the draft in the external editor."""

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

	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		self._history: list[str] = []
		self._history_index: int | None = None
		self._history_draft = ""

	def on_mount(self) -> None:
		# a blinking cursor pulls the eye away from the streaming transcript
		self.cursor_blink = False

	@property
	def chord_armed(self) -> bool:
		return self._chord_timer is not None

	def set_history(self, prompts: list[str]) -> None:
		"""Prepend durable prompts loaded from this and earlier sessions."""
		self._history = [*prompts, *self._history]
		self._reset_history_navigation()

	def _remember(self, text: str) -> None:
		self._history.append(text)
		self._reset_history_navigation()

	def _reset_history_navigation(self) -> None:
		self._history_index = None
		self._history_draft = ""

	def _show_history(self, text: str) -> None:
		self.load_text(text)
		self.move_cursor(self.document.end)

	def _history_up(self) -> None:
		if not self._history:
			return
		if self._history_index is None:
			self._history_draft = self.text
			self._history_index = len(self._history) - 1
		elif self._history_index > 0:
			self._history_index -= 1
		self._show_history(self._history[self._history_index])

	def _history_down(self) -> bool:
		if self._history_index is None:
			return False
		if self._history_index < len(self._history) - 1:
			self._history_index += 1
			self._show_history(self._history[self._history_index])
		else:
			self._show_history(self._history_draft)
			self._reset_history_navigation()
		return True

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
		if event.key == "up":
			event.stop()
			event.prevent_default()
			self._history_up()
			return
		if event.key == "down" and self._history_down():
			event.stop()
			event.prevent_default()
			return
		if event.key in ("enter", "alt+enter"):
			event.stop()
			event.prevent_default()
			text = self.text.strip()
			if text.startswith("/") and not text.startswith("/skill:"):
				self.post_message(self.CommandSubmitted(text))
				self.clear()
				self._reset_history_navigation()
			elif text:
				self._remember(text)
				self.post_message(self.Submitted(text, queue=event.key == "alt+enter"))
				self.clear()
			return
		if event.key == "ctrl+j":
			event.stop()
			event.prevent_default()
			self.insert("\n")
			return
		await super()._on_key(event)
