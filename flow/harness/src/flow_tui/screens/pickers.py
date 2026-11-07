"""Modal pickers for `/model`, `/resume`, and `/effort`.

All dismiss with a string result or `None` for cancel; the calling command owns
the API call, so a picker never touches the controller.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList
from textual.widgets.option_list import Option

from flow_harness.events import ReasoningEffort


class FilterPicker(ModalScreen[str | None]):
	"""A filter input over an option list; subclasses supply the options.

	Enter selects the highlighted option and dismisses with its id; with nothing
	highlighted it cancels, as does escape.
	"""

	BINDINGS: ClassVar = [Binding("escape", "cancel", "cancel")]
	placeholder: ClassVar[str] = "filter"

	def options(self, needle: str) -> Iterable[Option]:
		"""The options whose label matches the lower-cased filter text."""
		raise NotImplementedError

	def compose(self) -> ComposeResult:
		with Vertical(classes="picker"):
			yield Input(placeholder=self.placeholder)
			yield OptionList()

	def on_mount(self) -> None:
		self._refilter("")
		self.query_one(Input).focus()

	def _refilter(self, needle: str) -> None:
		options = self.query_one(OptionList)
		options.clear_options()
		options.add_options(self.options(needle.lower()))
		if options.option_count:
			options.highlighted = 0

	def on_input_changed(self, message: Input.Changed) -> None:
		self._refilter(message.value)

	def on_key(self, event) -> None:
		# focus stays in the filter; up/down drive the list underneath
		if event.key not in ("down", "up"):
			return
		options = self.query_one(OptionList)
		if not options.option_count:
			return
		event.stop()
		event.prevent_default()
		if options.highlighted is None:
			options.highlighted = 0 if event.key == "down" else options.option_count - 1
		else:
			step = 1 if event.key == "down" else -1
			options.highlighted = (options.highlighted + step) % options.option_count

	def on_input_submitted(self, message: Input.Submitted) -> None:
		options = self.query_one(OptionList)
		if options.highlighted is not None:
			self.dismiss(options.get_option_at_index(options.highlighted).id)
		else:
			self.dismiss(None)

	def on_option_list_option_selected(self, message: OptionList.OptionSelected) -> None:
		self.dismiss(message.option.id)

	def action_cancel(self) -> None:
		self.dismiss(None)


class ModelPicker(FilterPicker):
	"""Filterable list over the daemon's model catalog."""

	placeholder = "filter models"

	def __init__(self, models: list[dict]):
		super().__init__()
		self._models = models

	def options(self, needle: str) -> Iterable[Option]:
		return (
			Option(model["name"], id=model["name"])
			for model in self._models
			if needle in model["name"].lower()
		)


class SessionPicker(FilterPicker):
	"""Filterable list over the daemon's sessions; dismisses with the full session id."""

	placeholder = "filter sessions"

	def __init__(self, sessions: list[dict], current: str | None):
		super().__init__()
		self._sessions = sessions
		self._current = current

	def options(self, needle: str) -> Iterable[Option]:
		for info in self._sessions:
			parts = [info["session_id"][:8], f"{info['state']:<7}", info["model"]]
			if info.get("title"):
				parts.append(info["title"][:40])
			parts.append(info["cwd"])
			label = "  ".join(parts)
			if info["session_id"] == self._current:
				label += "  ← current"
			if needle in label.lower():
				yield Option(label, id=info["session_id"])


EFFORT_CHOICES: tuple[tuple[str, str], ...] = (
	("default", "provider default — no effort parameter sent"),
	("off", "disable reasoning where the provider allows it"),
	("minimal", ""),
	("low", ""),
	("medium", ""),
	("high", ""),
	("xhigh", ""),
	("max", ""),
)


class EffortPicker(ModalScreen[str | None]):
	"""Reasoning-effort ladder; dismisses with the chosen level or "default"."""

	BINDINGS: ClassVar = [Binding("escape", "cancel", "cancel")]

	def __init__(self, current: ReasoningEffort | None = None):
		super().__init__()
		self._current = current or "default"

	def compose(self) -> ComposeResult:
		with Vertical(classes="picker"):
			yield OptionList(
				*(Option(self._prompt(level, note), id=level) for level, note in EFFORT_CHOICES),
				id="effort-options",
			)

	def _prompt(self, level: str, note: str) -> str:
		marker = "●" if level == self._current else " "
		return f"{marker} {level:<8}{note}".rstrip()

	def on_mount(self) -> None:
		options = self.query_one(OptionList)
		options.highlighted = options.get_option_index(self._current)
		options.focus()

	def on_option_list_option_selected(self, message: OptionList.OptionSelected) -> None:
		self.dismiss(message.option.id)

	def action_cancel(self) -> None:
		self.dismiss(None)
