# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import frappe
from frappe import _
from frappe.model.document import Document

from flow.utils.system_generated import block_delete, block_rename, validate_immutable

if TYPE_CHECKING:
	from flow.flow.doctype.flow_run.flow_run import FlowRun
	from flow.flow.doctype.flow_session.flow_session import FlowSession
	from flow.lib.tool import Tool

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

	def validate(self):
		self._validate_max_iterations()
		self._ensure_knowledge_search_tool()
		validate_immutable(self, ("instructions", "max_iterations", "tools", "knowledge_bases"))

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

	def client_tool_config(self, session: str | None = None) -> dict[str, list[Any]]:
		"""The tools' schemas and which pause for approval. `session` binds attachment search."""
		tools = self.client_tools(session)
		return {
			"client_tools": [tool.to_dict() for tool in tools],
			"confirm_tools": [tool.name for tool in tools if tool.requires_confirmation],
		}

	def client_tools(self, session: str | None = None) -> list[Tool]:
		"""This agent's tools minus update_memory, which stays local until the new memory system."""
		from flow.memory.memory import MEMORY_TOOL_SLUG

		return [tool for tool in self._resolve_tools(session) if tool.name != MEMORY_TOOL_SLUG]

	def _resolve_tools(self, session: str | None = None) -> list[Tool]:
		from flow.memory.memory import MEMORY_TOOL_SLUG
		from flow.tools.builtins import (
			ATTACHMENT_SEARCH_SLUG,
			KNOWLEDGE_SEARCH_SLUG,
			bind_search_attachments,
			bind_search_knowledge,
			bind_update_memory,
		)

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
			elif tool_doc.name == ATTACHMENT_SEARCH_SLUG:
				resolved.append(bind_search_attachments(session))
			elif tool_doc.name == MEMORY_TOOL_SLUG:
				resolved.append(bind_update_memory(self.name))
			else:
				resolved.append(tool_doc.to_tool())
		return resolved

	def new_session(
		self,
		*,
		model: str | None = None,
		title: str | None = None,
		source: str = "Manual",
		auto_approve: bool = False,
	) -> FlowSession:
		"""Start a conversation driven by this agent on the flow server."""
		from flow.lib.session import new_session

		return new_session(self, model=model, title=title, source=source, auto_approve=auto_approve)

	def run(
		self,
		input: str,
		*,
		session: str | None = None,
		source: str = "Manual",
		trigger: str | None = None,
		reference_doctype: str | None = None,
		reference_name: str | None = None,
	) -> FlowRun:
		"""Start `input` and return its Running Flow Run, in a new or existing session."""
		from flow.lib.session import load_session, new_session

		if session:
			convo = load_session(session, agent=self.name)
		else:
			convo = new_session(self, source=source)
		return convo.chat(
			input,
			source=source,
			trigger=trigger,
			reference_doctype=reference_doctype,
			reference_name=reference_name,
		)
