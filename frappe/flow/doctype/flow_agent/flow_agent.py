# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING, Any

import frappe
from frappe import _
from frappe.model.document import Document

from flow.utils.system_generated import block_delete, block_rename, validate_immutable

if TYPE_CHECKING:
	from flow.flow.doctype.flow_run.flow_run import FlowRun
	from flow.lib.agent import Agent, Event
	from flow.lib.tool import Tool

DEFAULT_TOOL_SLUGS = ("describe", "read", "execute")
DEFAULT_MAX_ITERATIONS = 20


class FlowAgent(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from flow.flow.doctype.flow_agent_knowledge_base.flow_agent_knowledge_base import (
			FlowAgentKnowledgeBase,
		)
		from flow.flow.doctype.flow_agent_tool.flow_agent_tool import FlowAgentTool

		enabled: DF.Check
		instructions: DF.LongText
		is_system_generated: DF.Check
		knowledge_bases: DF.TableMultiSelect[FlowAgentKnowledgeBase]
		max_iterations: DF.Int
		model: DF.Link
		title: DF.Data
		tools: DF.TableMultiSelect[FlowAgentTool]
	# end: auto-generated types

	def on_trash(self):
		block_delete(self, always=True)

	def before_rename(self, old: str, _new: str, _merge: bool = False) -> None:
		block_rename(self, old)

	def before_insert(self):
		if not self.tools:
			for slug in DEFAULT_TOOL_SLUGS:
				if frappe.db.exists("Flow Tool", slug):
					self.append("tools", {"tool": slug})

	def validate(self):
		self._validate_max_iterations()
		self._ensure_knowledge_search_tool()
		validate_immutable(self)

	def _validate_max_iterations(self):
		if self.max_iterations is not None and self.max_iterations < 1:
			frappe.throw(_("Max Iterations must be at least 1."), title=_("Invalid Max Iterations"))

	def _ensure_knowledge_search_tool(self):
		"""A bound knowledge base is inert without the search tool. Keep them consistent
		so any agent with knowledge bases can actually query them, however it was created."""
		from flow.tools.builtins import KNOWLEDGE_SEARCH_SLUG

		if not self.knowledge_bases:
			return
		if any(row.tool == KNOWLEDGE_SEARCH_SLUG for row in self.tools):
			return
		if frappe.db.exists("Flow Tool", KNOWLEDGE_SEARCH_SLUG):
			self.append("tools", {"tool": KNOWLEDGE_SEARCH_SLUG})

	def assemble(self, *, model: str | None = None) -> Agent:
		"""Resolve this row into a runtime Agent. `model` overrides the saved agent's model for this build."""
		from flow.lib.agent import Agent
		from flow.lib.model import Model

		if not self.enabled:
			frappe.throw(_("Flow Agent {0} is disabled.").format(self.name), title=_("Disabled Agent"))

		model_name = model or self.model
		if not frappe.has_permission("Flow Model", "read", model_name):
			frappe.throw(
				_("You are not permitted to use Flow Model {0}.").format(model_name),
				frappe.PermissionError,
				title=_("Model Not Permitted"),
			)
		if not frappe.db.get_value("Flow Model", model_name, "enabled"):
			frappe.throw(_("Flow Model {0} is disabled.").format(model_name), title=_("Disabled Model"))

		return Agent(
			model=Model(model_name),
			name=self.name,
			instructions=self.instructions,
			tools=self._resolve_tools(),
			max_iterations=self.max_iterations or DEFAULT_MAX_ITERATIONS,
		)

	def _resolve_tools(self) -> list[Tool]:
		from flow.memory.memory import MEMORY_TOOL_SLUG
		from flow.tools.builtins import KNOWLEDGE_SEARCH_SLUG, bind_search_knowledge, bind_update_memory

		resolved: list[Tool] = []
		for row in self.tools:
			try:
				tool_doc = frappe.get_doc("Flow Tool", row.tool)
			except frappe.DoesNotExistError:
				frappe.log_error(title=f"Flow Agent {self.name!r}: tool {row.tool!r} not found, skipping")
				continue
			if not tool_doc.enabled:
				continue
			if tool_doc.name == KNOWLEDGE_SEARCH_SLUG:
				resolved.append(bind_search_knowledge([kb.knowledge_base for kb in self.knowledge_bases]))
			elif tool_doc.name == MEMORY_TOOL_SLUG:
				resolved.append(bind_update_memory(self.name))
			else:
				resolved.append(tool_doc.to_tool())
		return resolved

	def new_session(self, *, model: str | None = None, title: str | None = None):
		"""Start a conversation driven by this agent. Returns an FlowSession doc with runtime attached."""
		from flow.lib.session import new_session

		return new_session(self, model=model, title=title)

	def run(
		self,
		input: str,
		*,
		session: str | None = None,
		source: str = "Manual",
		trigger: str | None = None,
		reference_doctype: str | None = None,
		reference_name: str | None = None,
		auto_approve: bool = False,
		stream: bool = False,
	) -> FlowRun | Generator[Event]:
		"""Run `input` and persist as a Flow Run. Convenience wrapper over the session API:
		starts a conversation (or continues `session`) and calls `chat()`."""
		from flow.lib.session import load_session, new_session

		convo = load_session(session, agent=self.name) if session else new_session(self, source=source)
		return convo.chat(
			input,
			source=source,
			trigger=trigger,
			reference_doctype=reference_doctype,
			reference_name=reference_name,
			auto_approve=auto_approve,
			stream=stream,
		)

	def _snapshot(self, *, model: str | None = None) -> dict[str, Any]:
		return {
			"title": self.title,
			"model": model or self.model,
			"instructions": self.instructions,
			"tools": [row.tool for row in self.tools],
			"max_iterations": self.max_iterations or DEFAULT_MAX_ITERATIONS,
		}
