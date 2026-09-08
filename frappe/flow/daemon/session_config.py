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
	tools = agent._resolve_tools()
	config = {
		"session_id": session_id,
		"title": title,
		**model_config(model or agent.model),
		"system_prompt": agent.instructions or "",
		"tools": [],
		"extension_tools": [],
		"skills_enabled": False,
		"client_tools": [tool.to_dict() for tool in tools],
		"confirm_tools": [tool.name for tool in tools if tool.requires_confirmation],
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
