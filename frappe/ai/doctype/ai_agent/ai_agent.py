# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING, Any

import frappe
from frappe import _
from frappe.model.document import Document

if TYPE_CHECKING:
	from frappe.ai.agent import Agent, Event
	from frappe.ai.doctype.ai_run.ai_run import AIRun
	from frappe.ai.tool import Tool

DEFAULT_TOOL_SLUGS = ("introspect", "query", "execute", "ask_user")
DEFAULT_MAX_ITERATIONS = 10


class AIAgent(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.ai.doctype.ai_agent_tool.ai_agent_tool import AIAgentTool
		from frappe.types import DF

		enabled: DF.Check
		instructions: DF.LongText
		max_iterations: DF.Int
		model: DF.Link
		title: DF.Data
		tools: DF.TableMultiSelect[AIAgentTool]
	# end: auto-generated types

	def before_insert(self):
		if not self.tools:
			for slug in DEFAULT_TOOL_SLUGS:
				if frappe.db.exists("AI Tool", slug):
					self.append("tools", {"tool": slug})

	def validate(self):
		self._validate_max_iterations()
		self._deduplicate_tools()

	def _validate_max_iterations(self):
		if self.max_iterations is not None and self.max_iterations < 1:
			frappe.throw(_("Max Iterations must be at least 1."), title=_("Invalid Max Iterations"))

	def _deduplicate_tools(self):
		seen: set[str] = set()
		unique = []
		for row in self.tools:
			if row.tool in seen:
				continue
			seen.add(row.tool)
			unique.append(row)
		self.tools = unique

	def assemble(self, *, model: str | None = None) -> Agent:
		"""Resolve this row into a runtime Agent. `model` overrides the saved agent's model for this build."""
		from frappe.ai.agent import Agent
		from frappe.ai.model import Model

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
			tool_doc = frappe.get_doc("AI Tool", row.tool)
			if not tool_doc.enabled:
				continue
			resolved.append(tool_doc.to_tool())
		return resolved

	def run(
		self,
		input: str,
		*,
		source: str = "Manual",
		trigger: str | None = None,
		stream: bool = False,
	) -> AIRun | Generator[Event]:
		"""Assemble, run on `input`, and persist the result as an AI Run linked to this agent.

		With `stream=True`, returns a generator of agent Events instead of the AIRun row;
		the run is still created up-front (first event is `RunStarted` with its name) and
		persisted when the stream completes.
		"""
		from frappe.ai.doctype.ai_run.ai_run import create_run, stream_with_persistence
		from frappe.ai.doctype.ai_session.ai_session import derive_title

		agent = self.assemble()
		session = frappe.get_doc(
			{
				"doctype": "AI Session",
				"agent": self.name,
				"title": derive_title(input),
			}
		).insert(ignore_permissions=True)
		run = create_run(
			source=source,
			input=input,
			session=session.name,
			trigger=trigger,
			config_snapshot=self._snapshot(),
		)
		if stream:
			return stream_with_persistence(lambda: agent.run(input, stream=True), run)

		try:
			result = agent.run(input)
		except Exception as e:
			run.mark_failed(str(e))
			raise
		run.apply_result(result)
		return run

	def _snapshot(self, *, model: str | None = None) -> dict[str, Any]:
		return {
			"title": self.title,
			"model": model or self.model,
			"instructions": self.instructions,
			"tools": [row.tool for row in self.tools],
			"max_iterations": self.max_iterations or DEFAULT_MAX_ITERATIONS,
		}
