# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Turns a Flow Agent, its model and the current user into a flow server session."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import frappe
from frappe import _

from flow.daemon import lifecycle
from flow.flow.doctype.flow_agent.flow_agent import DEFAULT_MAX_ITERATIONS
from flow.lib.model import resolve_provider_credentials

if TYPE_CHECKING:
	from flow.flow.doctype.flow_agent.flow_agent import FlowAgent
	from flow.lib.tool import Tool

CALLBACK_METHOD = "flow.daemon.callback.tool_callback"


def build(
	agent: FlowAgent,
	*,
	session_id: str,
	title: str | None = None,
	model: str | None = None,
	auto_approve: bool = False,
) -> dict[str, Any]:
	"""The daemon session behind one Flow Session. The agent's tools travel as schemas
	only: the daemon calls this site back to run them, as the user, with the user's
	permissions. The daemon's own tools and skills stay off. Without `title` the daemon
	titles the session from its first message."""
	if not agent.enabled:
		frappe.throw(_("Flow Agent {0} is disabled.").format(agent.name), title=_("Disabled Agent"))
	tool_config = client_tool_config(agent)
	config = {
		"session_id": session_id,
		"title": title,
		**model_config(model or agent.model),
		"system_prompt": agent.instructions or "",
		"tools": [],
		"extension_tools": [],
		"skills_enabled": False,
		**tool_config,
		"auto_approve": auto_approve,
		"max_turns": agent.max_iterations or DEFAULT_MAX_ITERATIONS,
		"auto_compact": True,
		"callback_url": f"{lifecycle.site_url()}/api/method/{CALLBACK_METHOD}",
		"callback_token": frappe.conf.flow_server_secret,
		"user_context": {
			"site": frappe.local.site,
			"user": frappe.session.user,
			"agent": agent.name,
			"session": session_id,
		},
		"cwd": str(lifecycle.session_root()),
	}
	if frappe.conf.flow_callback_timeout:
		config["callback_timeout"] = frappe.conf.flow_callback_timeout
	return config


def model_config(model: str) -> dict[str, Any]:
	"""`model`, `api_key` and `api_base` for a Flow Model the user may use: the model's
	own credentials, else its provider's."""
	frappe.has_permission("Flow Model", "read", model, throw=True)
	doc = frappe.get_doc("Flow Model", model)
	if not doc.enabled:
		frappe.throw(_("Flow Model {0} is disabled.").format(model), title=_("Disabled Model"))
	provider = resolve_provider_credentials(doc.model_id)
	return {
		"model": doc.model_id,
		"api_key": doc.get_password("api_key", raise_exception=False) or provider.get("api_key"),
		"api_base": doc.base_url or provider.get("base_url"),
	}


def client_tools(agent: FlowAgent) -> list[Tool]:
	"""The agent's tools as the daemon sees them: all of them except update_memory. No
	memory travels to the daemon until the new memory system lands."""
	from flow.memory.memory import MEMORY_TOOL_SLUG

	return [tool for tool in agent._resolve_tools() if tool.name != MEMORY_TOOL_SLUG]


def client_tool_config(agent: FlowAgent) -> dict[str, list[Any]]:
	tools = client_tools(agent)
	return {
		"client_tools": [tool.to_dict() for tool in tools],
		"confirm_tools": [tool.name for tool in tools if tool.requires_confirmation],
	}


def sync_tool_sessions(tool_name: str) -> None:
	"""Refresh the daemon config of sessions whose agent uses this tool."""
	from flow.daemon.client import DaemonClient, DaemonError

	agents = set(frappe.get_all("Flow Agent Tool", filters={"tool": tool_name}, pluck="parent"))
	if not agents:
		return
	try:
		client = DaemonClient.for_site()
	except DaemonError as exc:
		frappe.log_error(title=f"Flow Tool {tool_name!r}: could not reach the flow server", message=str(exc))
		return
	with client:
		for agent_name in agents:
			config = client_tool_config(frappe.get_doc("Flow Agent", agent_name))
			sessions = frappe.get_all("Flow Session", filters={"agent": agent_name}, pluck="name")
			for session in sessions:
				try:
					client.patch_config(session, **config)
				except DaemonError as exc:
					if exc.status == 404:
						continue
					frappe.log_error(
						title=f"Flow Tool {tool_name!r}: could not refresh daemon session {session!r}",
						message=str(exc),
					)
					if exc.status is None:
						return
