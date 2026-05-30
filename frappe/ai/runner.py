# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import frappe
from frappe import _

if TYPE_CHECKING:
	from collections.abc import Generator

	from frappe.ai.agent import Agent, Event
	from frappe.ai.doctype.ai_run.ai_run import AIRun
	from frappe.ai.doctype.ai_session.ai_session import AISession


def start(
	*,
	input: str,
	agent: str | None = None,
	session: str | None = None,
	model: str | None = None,
	source: str = "Manual",
	trigger: str | None = None,
	stream: bool = False,
) -> AIRun | Generator[Event]:
	"""Run one turn: resolve-or-create the session, execute the agent, persist as an AI Run.

	Returns the AIRun row, or an event generator when `stream=True`. The session transcript is
	loaded and the new user message appended automatically — callers pass `input`, plus `session`
	for follow-up turns.
	"""
	from frappe.ai.doctype.ai_run.ai_run import create_run, stream_with_persistence

	session_doc = _resolve_session(session, agent, model, input)
	agent_runtime, snapshot = _build_runtime(session_doc)
	run_input = _build_run_input(session_doc, input)

	run = create_run(
		source=source,
		input=input,
		session=session_doc.name,
		trigger=trigger,
		config_snapshot=snapshot,
	)

	if stream:
		return stream_with_persistence(lambda: agent_runtime.run(run_input, stream=True), run)

	try:
		result = agent_runtime.run(run_input)
	except Exception as e:
		run.mark_failed(str(e))
		raise
	run.apply_result(result)
	return run


def resume(
	*,
	run_name: str,
	answers: dict[str, Any],
	stream: bool = False,
) -> AIRun | Generator[Event]:
	"""Resume a Paused run with the user's answers. Returns the AIRun row or an event generator."""
	from frappe.ai.doctype.ai_run.ai_run import stream_with_persistence

	run = frappe.get_doc("AI Run", run_name)
	_assert_run_owner(run)
	if run.status != "Paused":
		frappe.throw(
			_("Only Paused runs can be resumed (this run is {0}).").format(run.status),
			title=_("Cannot Resume"),
		)

	session_doc = frappe.get_doc("AI Session", run.session)
	messages = session_doc.transcript()
	if not messages:
		frappe.throw(_("This session has no transcript to resume from."))

	agent = _rebuild_agent(session_doc)

	if stream:
		return stream_with_persistence(lambda: agent.resume(messages, answers, stream=True), run)

	try:
		result = agent.resume(messages, answers)
	except Exception as e:
		run.mark_failed(str(e))
		raise
	run.apply_result(result)
	return run


def _resolve_session(
	session_name: str | None,
	agent_param: str | None,
	model_param: str | None,
	input_text: str,
) -> AISession:
	"""Load an existing session (with ownership + agent match) or create a new one. A model
	override given on an existing session is persisted as the new override."""
	from frappe.ai.doctype.ai_session.ai_session import derive_title

	if session_name:
		session_doc = frappe.get_doc("AI Session", session_name)
		_assert_session_owner(session_doc)
		if agent_param and agent_param != session_doc.agent:
			frappe.throw(
				_("This session is bound to agent {0} and cannot be switched.").format(session_doc.agent),
				title=_("Agent Mismatch"),
			)
		if model_param and model_param != session_doc.model:
			session_doc.model = model_param
			session_doc.save(ignore_permissions=True)
		return session_doc

	if agent_param:
		if not frappe.db.exists("AI Agent", agent_param):
			frappe.throw(_("AI Agent {0} not found.").format(agent_param), frappe.DoesNotExistError)
		frappe.has_permission("AI Agent", "read", agent_param, throw=True)
		agent_name = agent_param
	else:
		agent_name = _default_agent_name()

	return frappe.get_doc(
		{
			"doctype": "AI Session",
			"agent": agent_name,
			"model": model_param,
			"title": derive_title(input_text),
		}
	).insert(ignore_permissions=True)


def _default_agent_name() -> str:
	from frappe.ai.assistant import ASSISTANT_AGENT_TITLE

	if not frappe.db.exists("AI Agent", ASSISTANT_AGENT_TITLE):
		frappe.throw(
			_("The {0} agent is missing. Create an AI Model first to auto-provision it.").format(
				ASSISTANT_AGENT_TITLE
			),
			title=_("Missing Default Agent"),
		)
	return ASSISTANT_AGENT_TITLE


def _build_runtime(session_doc: AISession) -> tuple[Agent, dict[str, Any]]:
	"""Return (agent_runtime, config_snapshot) honoring the session's model override."""
	model = session_doc.model
	agent_doc = frappe.get_doc("AI Agent", session_doc.agent)
	return agent_doc.assemble(model=model), agent_doc._snapshot(model=model)


def _build_run_input(session_doc: AISession, new_input: str) -> str | list[dict[str, Any]]:
	"""Return the LLM input for this turn: a raw string on the first turn, or the session's
	transcript so far with the new user message appended. Blocks if a previous run on this
	session is still pending or in-flight."""
	blocking = frappe.db.get_value(
		"AI Run",
		{"session": session_doc.name, "status": ("in", ["Paused", "Running"])},
		"status",
		order_by="creation desc",
	)
	if blocking == "Paused":
		frappe.throw(
			_("This session has a paused run. Resume it before starting a new turn."),
			title=_("Run Paused"),
		)
	if blocking == "Running":
		frappe.throw(
			_("This session already has a run in progress."),
			title=_("Run In Progress"),
		)

	transcript = session_doc.transcript()
	if not transcript:
		return new_input

	transcript.append({"role": "user", "content": new_input})
	return transcript


def _rebuild_agent(session_doc: AISession) -> Agent:
	return frappe.get_doc("AI Agent", session_doc.agent).assemble(model=session_doc.model)


def _assert_session_owner(session_doc: AISession) -> None:
	if session_doc.owner == frappe.session.user:
		return
	if frappe.has_permission("AI Session", "write", session_doc):
		return
	frappe.throw(_("Not permitted to use this session."), frappe.PermissionError)


def _assert_run_owner(run: AIRun) -> None:
	if run.owner == frappe.session.user:
		return
	if frappe.has_permission("AI Run", "write", run):
		return
	frappe.throw(_("Not permitted to resume this run."), frappe.PermissionError)
