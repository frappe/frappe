# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import frappe
from frappe import _

if TYPE_CHECKING:
	from flow.flow.doctype.flow_run.flow_run import FlowRun
	from flow.flow.doctype.flow_session.flow_session import FlowSession
	from flow.lib.agent import Agent


def new_session(
	agent: Any = None, *, model: str | None = None, title: str | None = None, source: str = "Manual"
) -> FlowSession:
	"""Start a conversation. `agent` may be a code `Agent`, a Flow Agent doc, an agent name,
	or None for the default Assistant. Code agents leave the session's agent link empty.
	`source` records how it was started; "Trigger" sessions are hidden from the chat panel."""
	runtime, agent_name, session_model, snapshot = _resolve_new_agent(agent, model)
	doc = frappe.get_doc(
		{
			"doctype": "Flow Session",
			"agent": agent_name,
			"model": session_model,
			"title": title,
			"source": source,
		}
	).insert(ignore_permissions=True)
	doc._runtime = runtime
	doc._snapshot = snapshot
	return doc


def load_session(name: str, *, agent: Any = None, model: str | None = None) -> FlowSession:
	"""Resume an existing conversation by id. Doctype-backed sessions rebuild their runtime
	automatically; code-agent sessions require the same `Agent` to be passed again."""
	doc = frappe.get_doc("Flow Session", name)
	_assert_session_owner(doc)

	if isinstance(agent, str) and agent and doc.agent and agent != doc.agent:
		frappe.throw(
			_("This session is bound to agent {0} and cannot be switched.").format(doc.agent),
			title=_("Agent Mismatch"),
		)

	if model and model != doc.model:
		doc.model = model
		doc.save(ignore_permissions=True)

	doc._runtime, doc._snapshot = _resolve_existing_agent(doc, agent)
	return doc


def _resolve_new_agent(agent: Any, model: str | None) -> tuple[Agent, str | None, str | None, dict[str, Any]]:
	"""Return (runtime, agent_link, session_model, snapshot) for a brand-new session."""
	from flow.lib.agent import Agent

	if isinstance(agent, Agent):
		return agent, None, None, agent.snapshot()

	if agent is None:
		# The default Assistant is shared; no per-user read check (matches the desk default).
		agent_doc = frappe.get_doc("Flow Agent", _default_agent_name())
	else:
		agent_doc = frappe.get_doc("Flow Agent", agent) if isinstance(agent, str) else agent
		frappe.has_permission("Flow Agent", "read", agent_doc.name, throw=True)
	return agent_doc.assemble(model=model), agent_doc.name, (model or None), agent_doc._snapshot(model=model)


def _resolve_existing_agent(doc: FlowSession, agent: Any) -> tuple[Agent, dict[str, Any]]:
	"""Return (runtime, snapshot) for an existing session."""
	from flow.lib.agent import Agent

	if isinstance(agent, Agent):
		return agent, agent.snapshot()
	if doc.agent:
		agent_doc = frappe.get_doc("Flow Agent", doc.agent)
		return agent_doc.assemble(model=doc.model), agent_doc._snapshot(model=doc.model)
	frappe.throw(
		_("This session was created with a code agent; pass agent= to continue it."),
		title=_("Agent Required"),
	)


def _default_agent_name() -> str:
	from flow.assistant import ASSISTANT_AGENT_TITLE

	if not frappe.db.exists("Flow Agent", ASSISTANT_AGENT_TITLE):
		frappe.throw(
			_("The {0} agent is missing. Create a Flow Model first to auto-provision it.").format(
				ASSISTANT_AGENT_TITLE
			),
			title=_("Missing Default Agent"),
		)
	return ASSISTANT_AGENT_TITLE


def _assert_session_owner(doc: FlowSession) -> None:
	if doc.owner == frappe.session.user:
		return
	if frappe.has_permission("Flow Session", "write", doc):
		return
	frappe.throw(_("Not permitted to use this session."), frappe.PermissionError)


def assert_run_owner(run: FlowRun) -> None:
	if run.owner == frappe.session.user:
		return
	if frappe.has_permission("Flow Run", "write", run):
		return
	frappe.throw(_("Not permitted to resume this run."), frappe.PermissionError)
