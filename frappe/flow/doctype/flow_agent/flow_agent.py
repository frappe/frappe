# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

from html import escape
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

# The index rides in every session's prompt. With each description capped at 1024
# characters, this holds the block under ~33 KB however the skills are written.
MAX_SKILLS = 30

SKILL_INDEX_LEAD = (
	"Specialized instructions for specific tasks. When a task matches a skill's description, "
	"call load_skill with that name and follow what it returns."
)


class FlowAgent(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from flow.flow.doctype.flow_agent_knowledge_base.flow_agent_knowledge_base import (
			FlowAgentKnowledgeBase,
		)
		from flow.flow.doctype.flow_agent_skill.flow_agent_skill import FlowAgentSkill
		from flow.flow.doctype.flow_agent_tool.flow_agent_tool import FlowAgentTool

		enabled: DF.Check
		instructions: DF.LongText
		is_system_generated: DF.Check
		knowledge_bases: DF.TableMultiSelect[FlowAgentKnowledgeBase]
		max_iterations: DF.Int
		model: DF.Link
		skills: DF.TableMultiSelect[FlowAgentSkill]
		title: DF.Data
		tools: DF.TableMultiSelect[FlowAgentTool]
	# end: auto-generated types

	def on_trash(self):
		block_delete(self, always=True)

	def before_rename(self, old: str, _new: str, _merge: bool = False) -> None:
		block_rename(self, old)

	def validate(self):
		self._validate_max_iterations()
		self._validate_skills()
		self._ensure_knowledge_search_tool()
		validate_immutable(self, ("instructions", "max_iterations", "tools", "knowledge_bases", "skills"))

	def _validate_max_iterations(self):
		if self.max_iterations is not None and self.max_iterations < 1:
			frappe.throw(_("Max Iterations must be at least 1."), title=_("Invalid Max Iterations"))

	def _validate_skills(self):
		if len(self.skills) > MAX_SKILLS:
			frappe.throw(
				_("An agent can have at most {0} skills.").format(MAX_SKILLS),
				title=_("Too Many Skills"),
			)

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
		"""This agent's enabled tools, bound to `session` where needed."""
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
				resolved.append(bind_update_memory(self.name, session))
			else:
				resolved.append(tool_doc.to_tool())
		return resolved

	def skill_index(self) -> str:
		"""The `<available_skills>` block for this agent's enabled skills, "" when it has none.
		It rides in the system prompt, so a session's skills are fixed when it starts."""
		names = [row.skill for row in self.skills]
		if not names:
			return ""
		rows = frappe.get_all(
			"Flow Skill",
			filters={"name": ["in", names], "enabled": 1},
			fields=["name", "description"],
			order_by="name",
		)
		if not rows:
			return ""
		entries = "\n".join(
			f"  <skill>\n    <name>{_escape(row.name)}</name>\n"
			f"    <description>{_escape(_one_line(row.description))}</description>\n  </skill>"
			for row in rows
		)
		return f"\n\n<available_skills>\n{SKILL_INDEX_LEAD}\n{entries}\n</available_skills>"

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


def _escape(text: str) -> str:
	"""Escape for element content only: quotes are literal text here, not delimiters."""
	return escape(text, quote=False)


def _one_line(text: str) -> str:
	"""Descriptions are free text; the index gives each one a single line."""
	return " ".join((text or "").split())
