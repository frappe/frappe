# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import frappe
from frappe import _

if TYPE_CHECKING:
	from collections.abc import Generator

	from flow.ai.doctype.ai_run.ai_run import AIRun
	from flow.ai.doctype.ai_session.ai_session import AISession
	from flow.lib.agent import Agent, Event

# A "Running" run older than this is treated as abandoned (its stream died without
# persisting a terminal state), so it no longer blocks new turns in the session.
RUNNING_STALE_SECONDS = 300


class Session:
	"""Runtime handle over an AI Session: the persisted conversation plus the runtime that
	drives it. Create one with `new_session()` / `agent.new_session()`, resume with
	`load_session()`, and run turns with `chat()` / `resume()`."""

	def __init__(self, doc: AISession, runtime: Agent, snapshot: dict[str, Any]):
		self._doc = doc
		self._runtime = runtime
		self._snapshot = snapshot

	@property
	def id(self) -> str:
		return self._doc.name

	@property
	def doc(self) -> AISession:
		return self._doc

	def chat(
		self,
		input: str,
		*,
		source: str = "Manual",
		trigger: str | None = None,
		stream: bool = False,
	) -> AIRun | Generator[Event]:
		"""Run one turn and persist it as an AI Run. With `stream=True`, returns an event generator."""
		from flow.ai.doctype.ai_run.ai_run import create_run, stream_with_persistence

		self._doc.reload()
		self._assert_not_blocked()
		if not self._doc.title:
			self._doc.db_set("title", _derive_title(input))

		run_input = self._build_input(input)
		run = create_run(
			source=source,
			input=input,
			session=self._doc.name,
			trigger=trigger,
			config_snapshot=self._snapshot,
		)

		if stream:
			return stream_with_persistence(lambda: self._runtime.run(run_input, stream=True), run)

		try:
			result = self._runtime.run(run_input)
		except Exception as e:
			run.mark_failed(str(e))
			raise
		run.apply_result(result)
		return run

	def resume(self, answers: dict[str, Any], *, stream: bool = False) -> AIRun | Generator[Event]:
		"""Resume this session's paused run with the user's answers."""
		from flow.ai.doctype.ai_run.ai_run import stream_with_persistence

		run_name = frappe.db.get_value(
			"AI Run",
			{"session": self._doc.name, "status": "Paused"},
			"name",
			order_by="creation desc",
		)
		if not run_name:
			frappe.throw(_("This session has no paused run to resume."), title=_("Nothing to Resume"))
		run = frappe.get_doc("AI Run", run_name)

		self._doc.reload()
		messages = self._doc.transcript()
		if not messages:
			frappe.throw(_("This session has no transcript to resume from."))

		if stream:
			return stream_with_persistence(lambda: self._runtime.resume(messages, answers, stream=True), run)

		try:
			result = self._runtime.resume(messages, answers)
		except Exception as e:
			run.mark_failed(str(e))
			raise
		run.apply_result(result)
		return run

	def _build_input(self, new_input: str) -> str | list[dict[str, Any]]:
		"""First turn → the raw string (the agent prepends its system prompt). Later turns →
		the transcript so far with the new user message appended."""
		transcript = self._doc.transcript()
		if not transcript:
			return new_input
		transcript.append({"role": "user", "content": new_input})
		return transcript

	def _assert_not_blocked(self) -> None:
		blocking = frappe.db.get_value(
			"AI Run",
			{"session": self._doc.name, "status": ("in", ["Paused", "Running"])},
			["name", "status", "creation"],
			order_by="creation desc",
			as_dict=True,
		)
		if not blocking:
			return
		if blocking.status == "Paused":
			frappe.throw(
				_("This session has a paused run. Resume it before starting a new turn."),
				title=_("Run Paused"),
			)
		# A "Running" run whose stream died without persisting (client disconnect, restart)
		# would block the session forever. Recover it once it's clearly stale; otherwise a
		# genuinely in-progress turn still blocks concurrent sends.
		age = frappe.utils.time_diff_in_seconds(frappe.utils.now_datetime(), blocking.creation)
		if age > RUNNING_STALE_SECONDS:
			frappe.db.set_value(
				"AI Run",
				blocking.name,
				{"status": "Failed", "error": "Run abandoned: stream ended without completing."},
			)
			return
		frappe.throw(
			_("This session already has a run in progress."),
			title=_("Run In Progress"),
		)


def new_session(agent: Any = None, *, model: str | None = None, title: str | None = None) -> Session:
	"""Start a conversation. `agent` may be a code `Agent`, an AI Agent doc, an agent name,
	or None for the default Assistant. Code agents leave the session's agent link empty."""
	runtime, agent_name, session_model, snapshot = _resolve_new_agent(agent, model)
	doc = frappe.get_doc(
		{
			"doctype": "AI Session",
			"agent": agent_name,
			"model": session_model,
			"title": title,
		}
	).insert(ignore_permissions=True)
	return Session(doc, runtime, snapshot)


def load_session(name: str, *, agent: Any = None, model: str | None = None) -> Session:
	"""Resume an existing conversation by id. Doctype-backed sessions rebuild their runtime
	automatically; code-agent sessions require the same `Agent` to be passed again."""
	doc = frappe.get_doc("AI Session", name)
	_assert_session_owner(doc)

	if isinstance(agent, str) and agent and doc.agent and agent != doc.agent:
		frappe.throw(
			_("This session is bound to agent {0} and cannot be switched.").format(doc.agent),
			title=_("Agent Mismatch"),
		)

	if model and model != doc.model:
		doc.model = model
		doc.save(ignore_permissions=True)

	runtime, snapshot = _resolve_existing_agent(doc, agent)
	return Session(doc, runtime, snapshot)


def _resolve_new_agent(agent: Any, model: str | None) -> tuple[Agent, str | None, str | None, dict[str, Any]]:
	"""Return (runtime, agent_link, session_model, snapshot) for a brand-new session."""
	from flow.lib.agent import Agent

	if isinstance(agent, Agent):
		return agent, None, None, agent.snapshot()

	if agent is None:
		# The default Assistant is shared; no per-user read check (matches the desk default).
		agent_doc = frappe.get_doc("AI Agent", _default_agent_name())
	else:
		agent_doc = frappe.get_doc("AI Agent", agent) if isinstance(agent, str) else agent
		frappe.has_permission("AI Agent", "read", agent_doc.name, throw=True)
	return agent_doc.assemble(model=model), agent_doc.name, (model or None), agent_doc._snapshot(model=model)


def _resolve_existing_agent(doc: AISession, agent: Any) -> tuple[Agent, dict[str, Any]]:
	"""Return (runtime, snapshot) for an existing session."""
	from flow.lib.agent import Agent

	if isinstance(agent, Agent):
		return agent, agent.snapshot()
	if doc.agent:
		agent_doc = frappe.get_doc("AI Agent", doc.agent)
		return agent_doc.assemble(model=doc.model), agent_doc._snapshot(model=doc.model)
	frappe.throw(
		_("This session was created with a code agent; pass agent= to continue it."),
		title=_("Agent Required"),
	)


def _default_agent_name() -> str:
	from flow.assistant import ASSISTANT_AGENT_TITLE

	if not frappe.db.exists("AI Agent", ASSISTANT_AGENT_TITLE):
		frappe.throw(
			_("The {0} agent is missing. Create an AI Model first to auto-provision it.").format(
				ASSISTANT_AGENT_TITLE
			),
			title=_("Missing Default Agent"),
		)
	return ASSISTANT_AGENT_TITLE


def _derive_title(text: str) -> str:
	from flow.ai.doctype.ai_session.ai_session import derive_title

	return derive_title(text)


def _assert_session_owner(doc: AISession) -> None:
	if doc.owner == frappe.session.user:
		return
	if frappe.has_permission("AI Session", "write", doc):
		return
	frappe.throw(_("Not permitted to use this session."), frappe.PermissionError)


def assert_run_owner(run: AIRun) -> None:
	if run.owner == frappe.session.user:
		return
	if frappe.has_permission("AI Run", "write", run):
		return
	frappe.throw(_("Not permitted to resume this run."), frappe.PermissionError)
