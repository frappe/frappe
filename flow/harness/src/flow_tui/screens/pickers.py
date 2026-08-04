"""Modal pickers for `/model` and `/effort`.

Both dismiss with a string result or `None` for cancel; the calling command owns
the API call, so a picker never touches the controller. The model picker's Enter
with nothing highlighted submits the raw filter text — the free-text escape hatch
for models the catalog missed.
"""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList
from textual.widgets.option_list import Option

from flow.events import ReasoningEffort


class ModelPicker(ModalScreen[str | None]):
	"""Filterable list over the daemon's model catalog.

	Enter selects the highlighted option; when the filter matches nothing, Enter
	submits the filter text verbatim. Escape cancels.
	"""

	BINDINGS: ClassVar = [Binding("escape", "cancel", "cancel")]

	def __init__(self, models: list[dict]):
		super().__init__()
		self._models = models

	def compose(self) -> ComposeResult:
		with Vertical(classes="picker"):
			yield Input(placeholder="filter models — free text sends as-is", id="model-filter")
			yield OptionList(id="model-options")

	def on_mount(self) -> None:
		self._refilter("")
		self.query_one(Input).focus()

	def _refilter(self, needle: str) -> None:
		options = self.query_one(OptionList)
		options.clear_options()
		needle = needle.lower()
		options.add_options(
			Option(f"{model['name']}  ·  {model['provider']}", id=model["name"])
			for model in self._models
			if needle in model["name"].lower()
		)
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
			self.dismiss(message.value.strip() or None)

	def on_option_list_option_selected(self, message: OptionList.OptionSelected) -> None:
		self.dismiss(message.option.id)

	def action_cancel(self) -> None:
		self.dismiss(None)


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
