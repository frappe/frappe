# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Flow Agents and tools defined in code."""

from __future__ import annotations

import importlib
import sys
from typing import TYPE_CHECKING

import frappe
from frappe import _
from frappe.flow.lib.tool import Tool
from frappe.flow.utils.system_generated import log_skipped, skip_if_invalid

if TYPE_CHECKING:
	from collections.abc import Iterator

	from frappe.flow.doctype.flow_run.flow_run import FlowRun
	from frappe.flow.doctype.flow_session.flow_session import FlowSession
	from frappe.flow.knowledge import Knowledge

DEFAULT_MAX_ITERATIONS = 100


def sync_agents(_app: str | None = None) -> None:
	"""Write every agent the installed apps declare through the `flow_agents` hook, whose
	entries name functions returning a list of Agents. Runs after migrate and app installs.
	An agent that cannot be written, or named like one declared before it, is skipped and logged,
	along with its sub-agents and tools."""
	hooked: list[Agent] = []
	for path in frappe.get_hooks("flow_agents"):
		with skip_if_invalid(f"Flow Agents of {path} skipped"):
			hooked.extend(frappe.get_attr(path)())
	declared: dict[str, Agent] = {}
	for agent in hooked:
		for item in _with_sub_agents(agent):
			declared.setdefault(item.name, item)
		# one definition may be listed twice
		duplicate = next((item for item in _with_sub_agents(agent) if declared[item.name] is not item), None)
		if duplicate:
			log_skipped(
				f"Flow Agent {agent.name} skipped",
				_("Flow Agent {0} is declared more than once.").format(duplicate.name),
			)
			continue
		with skip_if_invalid(f"Flow Agent {agent.name} skipped"):
			agent.sync()


def _with_sub_agents(agent: Agent) -> Iterator[Agent]:
	"""`agent`, then every sub-agent below it."""
	yield agent
	for child in agent.sub_agents:
		yield from _with_sub_agents(child)


def sync_tools(_app: str | None = None) -> None:
	"""Write each `@tool` the installed apps list under the `flow_tools` hook as a locked Imported
	Flow Tool, for any agent to attach. Runs after migrate and app installs. A tool that cannot be
	written is skipped and logged."""
	for path in frappe.get_hooks("flow_tools"):
		with skip_if_invalid(f"Flow Tool {path} skipped"):
			_ensure_tool(frappe.get_attr(path))


class Agent:
	"""A Flow Agent defined in code.

	Constructing one touches nothing. `sync()` writes the definition to the site as a
	system-generated Flow Agent doc, plus an Imported Flow Tool for each `@tool` function;
	Flow does that for the agents listed under the `flow_agents` hook. The desk can enable or
	disable them and switch the agent's model, nothing else. Tools must be module-level
	functions in an installed app, since the flow server calls them back by import path.
	The model calls them `<app>__<tool name>`, like `crm__read_records`.
	`sub_agents` are Agents this one may hand a task to; they are synced before it.
	`skills` are Flow Skill names. One without an app prefix, like `onboarding`, is this app's
	skill if it ships one, else the site's skill of that name.
	The doc is named and titled `<app>/<name>`, after the app whose code builds the Agent.
	"""

	def __init__(
		self,
		*,
		name: str,
		model: str,
		instructions: str,
		description: str = "",
		tools: list[Tool] | None = None,
		knowledge: Knowledge | list[Knowledge] | None = None,
		skills: list[str] | None = None,
		sub_agents: list[Agent] | None = None,
		max_iterations: int = DEFAULT_MAX_ITERATIONS,
		auto_approve: bool = False,
	):
		if knowledge and not isinstance(knowledge, list):
			knowledge = [knowledge]
		# the calling module's app, found the way namedtuple finds its module
		self.app = sys._getframe(1).f_globals["__name__"].split(".", 1)[0]
		self.name = f"{self.app}/{name}"
		self.model = model
		self.instructions = instructions
		self.description = description
		self.tools = list(tools or [])
		self.knowledge = list(knowledge or [])
		self.skills = list(skills or [])
		self.sub_agents = list(sub_agents or [])
		self.max_iterations = max_iterations
		self.auto_approve = auto_approve

	def sync(self) -> None:
		"""Write this definition to the site. The model is set only when the doc is created,
		or when its model is gone: switching it otherwise is the site's choice."""
		for child in self.sub_agents:
			child.sync()
		if frappe.db.exists("Flow Agent", self.name):
			doc = frappe.get_doc("Flow Agent", self.name)
			if not doc.is_system_generated:
				frappe.throw(
					_("Flow Agent {0} already exists and is not owned by code.").format(self.name),
					title=_("Agent Conflict"),
				)
			if not frappe.db.exists("Flow Model", doc.model):
				doc.model = self.model
		else:
			doc = frappe.get_doc(
				{"doctype": "Flow Agent", "title": self.name, "app": self.app, "model": self.model}
			)
		doc.description = self.description
		doc.instructions = self.instructions
		doc.max_iterations = self.max_iterations
		doc.is_system_generated = 1
		doc.set("tools", [{"tool": _ensure_tool(tool)} for tool in self.tools])
		doc.set("knowledge_bases", [{"knowledge_base": kb.name} for kb in self.knowledge])
		doc.set("skills", [{"skill": _skill_name(self.app, name)} for name in self.skills])
		doc.set("sub_agents", [{"agent": child.name} for child in self.sub_agents])
		doc.save(ignore_permissions=True)

	def new_session(self, *, title: str | None = None) -> FlowSession:
		"""Start a conversation with this agent on the flow server."""
		from frappe.flow.lib.session import new_session

		return new_session(self.name, title=title, auto_approve=self.auto_approve)

	def run(self, input: str, *, on_complete: str | None = None) -> FlowRun:
		"""Start `input` in a new session and return its Running Flow Run without waiting.
		Once the run ends, Flow calls the function at the dotted path `on_complete` with it."""
		return self.new_session().chat(input, on_complete=on_complete)


def with_app_prefix(app: str, name: str) -> str:
	"""`<app>/<name>`, unless `name` already has an app prefix like `crm/onboarding`."""
	return name if "/" in name else f"{app}/{name}"


def _skill_name(app: str, name: str) -> str:
	"""The skill `app`'s code means by `name`: its own `<app>/<name>` if it ships one, else `name`."""
	own = with_app_prefix(app, name)
	return own if frappe.db.exists("Flow Skill", own) else name


def _ensure_tool(tool: Tool) -> str:
	"""The name of `tool`'s Imported Flow Tool, created or brought up to date: `<app>/<tool name>`.
	A tool moved to another module keeps its row."""
	import_path = _tool_import_path(tool)
	name = f"{import_path.split('.', 1)[0]}/{tool.name}"
	definition = {
		"import_path": import_path,
		"description": tool.description,
		"requires_confirmation": int(tool.requires_confirmation),
		"background": int(tool.background is True),
		"is_system_generated": 1,
	}
	row = frappe.db.get_value("Flow Tool", name, list(definition), as_dict=True)
	if row and row.import_path != import_path and _exports_another(row.import_path, tool):
		frappe.throw(
			_("Tools {0} and {1} are both named {2}. Name one differently with @tool(name=...).").format(
				row.import_path, import_path, tool.name
			),
			title=_("Tool Conflict"),
		)
	if row and all(row.get(key) == value for key, value in definition.items()):
		return name
	if row:
		doc = frappe.get_doc("Flow Tool", name)
		doc.update(definition)
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Flow Tool",
				"slug": name,
				"title": tool.name.replace("_", " ").title(),
				"type": "Imported",
				**definition,
			}
		)
		doc.insert(ignore_permissions=True)
	return name


def _exports_another(import_path: str, tool: Tool) -> bool:
	"""Whether `import_path` still exports a Tool named like `tool` but other than it, rather than
	`tool` having moved away from there."""
	try:
		other = frappe.get_attr(import_path)
	except (ImportError, AttributeError):
		return False
	return isinstance(other, Tool) and other is not tool and other.name == tool.name


def _tool_import_path(tool: Tool) -> str:
	"""The installed-app module attribute that exports this Tool for callback imports."""
	module_name = tool.func.__module__
	if module_name.split(".", 1)[0] in frappe.get_installed_apps():
		try:
			module = importlib.import_module(module_name)
		except Exception:
			pass
		else:
			for name, value in vars(module).items():
				if value is tool:
					return f"{module_name}.{name}"
	frappe.throw(
		_("Tool {0} must be exported as a module-level attribute by an installed app.").format(tool.name),
		title=_("Invalid Tool"),
	)
