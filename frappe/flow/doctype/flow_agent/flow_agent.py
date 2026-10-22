# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING, Any

import frappe
from frappe import _
from frappe.flow.utils.system_generated import block_delete, block_rename, validate_immutable
from frappe.model.document import Document
from frappe.utils import get_fullname, today
from frappe.utils.jinja import get_jenv, safe_render_flags

if TYPE_CHECKING:
	from frappe.flow.doctype.flow_run.flow_run import FlowRun
	from frappe.flow.doctype.flow_session.flow_session import FlowSession
	from frappe.flow.lib.tool import Tool

DEFAULT_MAX_ITERATIONS = 100

# Skills bound to this agent; global ones add MAX_GLOBAL_SKILLS more. The index rides in
# every session's prompt, so both caps together bound it however the skills are written.
# Agents defined in code are not capped: the Assistant gets every installed app's skills.
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
		from frappe.core.doctype.has_role.has_role import HasRole
		from frappe.flow.doctype.flow_agent_knowledge_base.flow_agent_knowledge_base import (
			FlowAgentKnowledgeBase,
		)
		from frappe.flow.doctype.flow_agent_skill.flow_agent_skill import FlowAgentSkill
		from frappe.flow.doctype.flow_agent_sub_agent.flow_agent_sub_agent import FlowAgentSubAgent
		from frappe.flow.doctype.flow_agent_tool.flow_agent_tool import FlowAgentTool
		from frappe.types import DF

		description: DF.SmallText | None
		enabled: DF.Check
		instructions: DF.LongText
		is_system_generated: DF.Check
		knowledge_bases: DF.TableMultiSelect[FlowAgentKnowledgeBase]
		max_iterations: DF.Int
		model: DF.Link
		roles: DF.TableMultiSelect[HasRole]
		skills: DF.TableMultiSelect[FlowAgentSkill]
		sub_agents: DF.TableMultiSelect[FlowAgentSubAgent]
		title: DF.Data
		token_budget: DF.Int
		tools: DF.TableMultiSelect[FlowAgentTool]
	# end: auto-generated types

	def on_update(self):
		from frappe.flow.lib.session import warn_existing_sessions

		before = self.get_doc_before_save()
		if before and (
			[row.tool for row in before.tools] != [row.tool for row in self.tools]
			or [row.agent for row in before.sub_agents] != [row.agent for row in self.sub_agents]
		):
			warn_existing_sessions([self.name])

	def on_trash(self):
		from frappe.flow.assistant.assistant import ASSISTANT_AGENT_TITLE

		block_delete(self, always=self.name == ASSISTANT_AGENT_TITLE)

	def before_rename(self, old: str, _new: str, _merge: bool = False) -> None:
		block_rename(self, old)

	def after_rename(self, old: str, new: str, _merge: bool = False) -> None:
		from frappe.flow.memory import store

		store.rename_agent(old, new)

	def validate(self):
		from frappe.flow.assistant.assistant import ASSISTANT_AGENT_TITLE

		self._validate_max_iterations()
		self._validate_token_budget()
		self._validate_skills()
		self._validate_sub_agents()
		self.render_instructions()
		self._ensure_knowledge_search_tool()
		validate_immutable(
			self,
			(
				"description",
				"instructions",
				"max_iterations",
				"tools",
				# the site may add skills and knowledge to the assistant
				*(() if self.name == ASSISTANT_AGENT_TITLE else ("knowledge_bases", "skills")),
				"sub_agents",
			),
		)
		# After the guard: attaching a tool is our side effect of the skills or sub-agents the caller
		# set, so a refused edit names what the caller actually changed, not our tools row.
		self._ensure_skill_tool()
		self._ensure_subagent_tool()

	def _validate_max_iterations(self):
		if self.max_iterations is not None and self.max_iterations < 1:
			frappe.throw(_("Max Iterations must be at least 1."), title=_("Invalid Max Iterations"))

	def _validate_token_budget(self):
		if (self.token_budget or 0) < 0:
			frappe.throw(_("Token Budget cannot be negative."), title=_("Invalid Token Budget"))

	def _validate_skills(self):
		if len(self.skills) > MAX_SKILLS and not self.is_system_generated:
			frappe.throw(
				_("An agent can bind at most {0} skills.").format(MAX_SKILLS),
				title=_("Too Many Skills"),
			)

	def _validate_sub_agents(self):
		if any(row.agent == self.name for row in self.sub_agents):
			frappe.throw(_("An agent cannot be its own sub-agent."), title=_("Invalid Sub-agent"))

	def _ensure_knowledge_search_tool(self):
		"""A bound knowledge base is inert without the search tool. Keep them consistent
		so any agent with knowledge bases can actually query them, however it was created."""
		from frappe.flow.tools.builtins import KNOWLEDGE_SEARCH_SLUG

		if not self.knowledge_bases:
			return
		if any(row.tool == KNOWLEDGE_SEARCH_SLUG for row in self.tools):
			return
		if frappe.db.exists("Flow Tool", KNOWLEDGE_SEARCH_SLUG):
			self.append("tools", {"tool": KNOWLEDGE_SEARCH_SLUG})

	def _ensure_skill_tool(self):
		"""A bound skill is inert without the tool that loads it, same as a knowledge base
		without its search tool."""
		from frappe.flow.tools.builtins import SKILL_TOOL_SLUG

		if not self.skills:
			return
		if any(row.tool == SKILL_TOOL_SLUG for row in self.tools):
			return
		if frappe.db.exists("Flow Tool", SKILL_TOOL_SLUG):
			self.append("tools", {"tool": SKILL_TOOL_SLUG})

	def _ensure_subagent_tool(self):
		"""A bound sub-agent is inert without the tool that runs it."""
		from frappe.flow.tools.builtins import SUBAGENT_TOOL_SLUG

		if not self.sub_agents:
			return
		if any(row.tool == SUBAGENT_TOOL_SLUG for row in self.tools):
			return
		if frappe.db.exists("Flow Tool", SUBAGENT_TOOL_SLUG):
			self.append("tools", {"tool": SUBAGENT_TOOL_SLUG})

	def client_tool_config(self, session: str | None = None) -> dict[str, list[Any]]:
		"""The tools' schemas and which pause for approval. `session` binds attachment search."""
		tools = self.client_tools(session)
		return {
			"client_tools": [tool.to_dict() for tool in tools],
			"confirm_tools": [tool.name for tool in tools if tool.requires_confirmation],
		}

	def client_tools(self, session: str | None = None) -> list[Tool]:
		"""This agent's enabled tools, bound to `session` where needed."""
		from frappe.flow.memory.memory import MEMORY_TOOL_SLUG
		from frappe.flow.tools.builtins import (
			ATTACHMENT_SEARCH_SLUG,
			KNOWLEDGE_SEARCH_SLUG,
			SERVER_TOOL_SLUGS,
			SKILL_TOOL_SLUG,
			bind_load_skill,
			bind_search_attachments,
			bind_search_knowledge,
			bind_update_memory,
		)

		resolved: list[Tool] = []
		for tool_doc in self._enabled_tool_docs():
			if tool_doc.name in SERVER_TOOL_SLUGS or tool_doc.type == "Server":
				continue
			if tool_doc.name == KNOWLEDGE_SEARCH_SLUG:
				resolved.append(bind_search_knowledge([kb.knowledge_base for kb in self.knowledge_bases]))
			elif tool_doc.name == ATTACHMENT_SEARCH_SLUG:
				resolved.append(bind_search_attachments(session))
			elif tool_doc.name == MEMORY_TOOL_SLUG:
				resolved.append(bind_update_memory(self.name, session))
			elif tool_doc.name == SKILL_TOOL_SLUG:
				resolved.append(bind_load_skill(self.name))
			else:
				resolved.append(tool_doc.to_tool())
		return resolved

	def server_tools(self) -> list[str]:
		"""Enabled daemon tools selected for this agent."""
		from frappe.flow.tools.builtins import SERVER_TOOL_SLUGS

		return [tool.name for tool in self._enabled_tool_docs() if tool.name in SERVER_TOOL_SLUGS]

	def subagent_configs(self, session: str | None, user_context: dict[str, Any]) -> list[dict[str, Any]]:
		"""The enabled sub-agents as flow server `subagents` entries: each on its own model, prompt
		and tools, calling back as itself. Their models come with this agent, like their tools."""
		from frappe.flow.lib.model import model_config

		configs = []
		for row in self.sub_agents:
			child = frappe.get_doc("Flow Agent", row.agent)
			if not child.enabled:
				continue
			if not frappe.db.get_value("Flow Model", child.model, "enabled"):
				frappe.throw(
					_("Sub-agent {0} runs on Flow Model {1}, which is disabled.").format(
						child.name, child.model
					),
					title=_("Disabled Model"),
				)
			configs.append(
				{
					"name": child.name,
					"description": _one_line(child.description),
					**model_config(child.model, check_permission=False),
					**child.session_tool_config(session),
					"max_turns": child.max_iterations or DEFAULT_MAX_ITERATIONS,
					"user_context": {**user_context, "agent": child.name},
				}
			)
		return configs

	def session_tool_config(self, session: str | None = None) -> dict[str, Any]:
		"""Complete tool configuration for one daemon session."""
		from frappe.flow.daemon import lifecycle
		from frappe.flow.tools.builtins import SOURCE_TOOL_SLUGS

		server_tools = self.server_tools()
		return {
			"system_prompt": self.render_instructions()
			+ self.skill_index()
			+ lifecycle.app_source_prompt([name for name in server_tools if name in SOURCE_TOOL_SLUGS]),
			"tools": server_tools,
			"extension_tools": self.extension_tools(),
			**self.client_tool_config(session),
		}

	def render_instructions(self) -> str:
		"""The instructions with their Jinja tags filled in for the current user."""
		user = frappe.session.user
		context = {"user": user, "full_name": get_fullname(user), "today": today()}
		try:
			# not render_template: it misreads "x.md" and ".__" text
			with safe_render_flags():
				return get_jenv().from_string(self.instructions or "").render(context)
		except Exception as e:
			frappe.throw(
				_(
					"Could not fill in the instructions: {0}. To keep Jinja as plain text, wrap it in {1}."
				).format(str(e).rstrip("."), "{% raw %}…{% endraw %}"),
				title=_("Invalid Instructions"),
			)

	def extension_tools(self) -> list[str]:
		"""Enabled flow server extension tools selected for this agent."""
		return [tool.name for tool in self._enabled_tool_docs() if tool.type == "Server"]

	def _enabled_tool_docs(self):
		for row in self.tools:
			try:
				tool_doc = frappe.get_doc("Flow Tool", row.tool)
			except frappe.DoesNotExistError:
				frappe.log_error(title=f"Flow Agent {self.name!r}: tool {row.tool!r} not found, skipping")
				continue
			if tool_doc.enabled:
				yield tool_doc

	def skill_index(self) -> str:
		"""The `<available_skills>` block for this agent's visible skills, "" when there are none.
		It rides in the system prompt, so a session's skills are fixed when it starts."""
		rows = self.visible_skills("description")
		if not rows:
			return ""
		entries = "\n".join(
			f"  <skill>\n    <name>{_escape(row.name)}</name>\n"  # nosemgrep: string-concat-in-list
			f"    <description>{_escape(_one_line(row.description))}</description>\n  </skill>"
			for row in rows
		)
		return f"\n\n<available_skills>\n{SKILL_INDEX_LEAD}\n{entries}\n</available_skills>"

	def visible_skills(self, *fields: str) -> list[dict[str, Any]]:
		"""Enabled skills this agent can load, by name: every global one plus its own, and none
		at all without the tool that loads them, so the index never advertises what it can't."""
		from frappe.flow.tools.builtins import SKILL_TOOL_SLUG

		if not any(row.tool == SKILL_TOOL_SLUG for row in self.tools):
			return []
		return self._skills(fields)

	def invocable_skills(self) -> list[dict[str, Any]]:
		"""Skills a user may start with `/skill:<command>`: the bound and global ones flagged for
		it. No tool gate: the instructions ride in the message, not through load_skill."""
		from frappe.flow.doctype.flow_skill.flow_skill import skill_command

		return [
			{**row, "command": skill_command(row.name)}
			for row in self._skills(("description",), user_invocable=1)
		]

	def _skills(self, fields: tuple[str, ...], **filters: Any) -> list[dict[str, Any]]:
		return frappe.get_all(
			"Flow Skill",
			filters={"enabled": 1, **filters},
			or_filters=[["is_global", "=", 1], ["name", "in", [row.skill for row in self.skills]]],
			fields=["name", *fields],
			order_by="name",
		)

	def new_session(
		self,
		*,
		model: str | None = None,
		title: str | None = None,
		source: str = "Manual",
		auto_approve: bool = False,
	) -> FlowSession:
		"""Start a conversation driven by this agent on the flow server."""
		from frappe.flow.lib.session import new_session

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
		on_complete: str | None = None,
	) -> FlowRun:
		"""Start `input` and return its Running Flow Run, in a new or existing session.
		Once the run ends, Flow calls the function at the dotted path `on_complete` with it."""
		from frappe.flow.lib.session import load_session, new_session

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
			on_complete=on_complete,
		)


def _escape(text: str) -> str:
	"""Escape for element content only: quotes are literal text here, not delimiters."""
	return escape(text, quote=False)


def _one_line(text: str) -> str:
	"""Descriptions are free text; the index gives each one a single line."""
	return " ".join((text or "").split())
