# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING, Any

import frappe
from frappe import _
from frappe.model.document import Document

if TYPE_CHECKING:
	from flow.ai.doctype.ai_run.ai_run import AIRun
	from flow.lib.agent import Agent, Event
	from flow.lib.tool import Tool

DEFAULT_TOOL_SLUGS = ("describe", "read", "execute")
DEFAULT_MAX_ITERATIONS = 10


class AIAgent(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from flow.ai.doctype.ai_agent_tool.ai_agent_tool import AIAgentTool

		enabled: DF.Check
		instructions: DF.LongText
		is_system_generated: DF.Check
		max_iterations: DF.Int
		model: DF.Link
		title: DF.Data
		tools: DF.TableMultiSelect[AIAgentTool]
	# end: auto-generated types

	def on_trash(self):
		if self.is_system_generated:
			frappe.throw(
				_("Cannot delete system-generated agent {0}.").format(self.name),
				title=_("Protected"),
			)

	def before_rename(self, old: str, _new: str, _merge: bool = False) -> None:
		if self.is_system_generated:
			frappe.throw(
				_("Cannot rename system-generated agent {0}.").format(old),
				title=_("Protected"),
			)

	def before_insert(self):
		if not self.tools:
			for slug in DEFAULT_TOOL_SLUGS:
				if frappe.db.exists("AI Tool", slug):
					self.append("tools", {"tool": slug})

	def validate(self):
		self._validate_max_iterations()

	def _validate_max_iterations(self):
		if self.max_iterations is not None and self.max_iterations < 1:
			frappe.throw(_("Max Iterations must be at least 1."), title=_("Invalid Max Iterations"))

	def assemble(self, *, model: str | None = None) -> Agent:
		"""Resolve this row into a runtime Agent. `model` overrides the saved agent's model for this build."""
		from flow.lib.agent import Agent
		from flow.lib.model import Model

		if not self.enabled:
			frappe.throw(_("AI Agent {0} is disabled.").format(self.name), title=_("Disabled Agent"))

		model_name = model or self.model
		if not frappe.db.get_value("AI Model", model_name, "enabled"):
			frappe.throw(_("AI Model {0} is disabled.").format(model_name), title=_("Disabled Model"))

		return Agent(
			model=Model(model_name),
			name=self.name,
			instructions=self.instructions,
			tools=self._resolve_tools(),
			max_iterations=self.max_iterations or DEFAULT_MAX_ITERATIONS,
		)

	def _resolve_tools(self) -> list[Tool]:
		resolved: list[Tool] = []
		for row in self.tools:
			try:
				tool_doc = frappe.get_doc("AI Tool", row.tool)
			except frappe.DoesNotExistError:
				frappe.log_error(title=f"AI Agent {self.name!r}: tool {row.tool!r} not found, skipping")
				continue
			if not tool_doc.enabled:
				continue
			resolved.append(tool_doc.to_tool())
		return resolved

	def new_session(self, *, model: str | None = None, title: str | None = None):
		"""Start a conversation driven by this agent. Returns an AISession doc with runtime attached."""
		from flow.lib.session import new_session

		return new_session(self, model=model, title=title)

	def run(
		self,
		input: str,
		*,
		session: str | None = None,
		source: str = "Manual",
		trigger: str | None = None,
		stream: bool = False,
	) -> AIRun | Generator[Event]:
		"""Run `input` and persist as an AI Run. Convenience wrapper over the session API:
		starts a conversation (or continues `session`) and calls `chat()`."""
		from flow.lib.session import load_session, new_session

		convo = load_session(session, agent=self.name) if session else new_session(self)
		return convo.chat(input, source=source, trigger=trigger, stream=stream)

	def _snapshot(self, *, model: str | None = None) -> dict[str, Any]:
		return {
			"title": self.title,
			"model": model or self.model,
			"instructions": self.instructions,
			"tools": [row.tool for row in self.tools],
			"max_iterations": self.max_iterations or DEFAULT_MAX_ITERATIONS,
		}
