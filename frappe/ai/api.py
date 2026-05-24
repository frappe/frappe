# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import frappe
from frappe import _

if TYPE_CHECKING:
	from frappe.ai.doctype.ai_run.ai_run import AIRun


@frappe.whitelist()
def start_run(input: str, agent: str | None = None) -> dict[str, Any]:
	"""Start a new AI Run. Pass `agent` to use a saved AI Agent, omit it to use the assistant."""
	if not isinstance(input, str) or not input.strip():
		frappe.throw(_("Input is required."), title=_("Invalid Input"))

	if agent:
		agent_doc = frappe.get_doc("AI Agent", agent)
		run = agent_doc.run(input)
	else:
		from frappe.ai.assistant import run_assistant

		run = run_assistant(input)

	return _summarize(run)


@frappe.whitelist()
def resume_run(run_name: str, answers: dict[str, Any] | str) -> dict[str, Any]:
	"""Resume a Paused AI Run by answering its pending questions (keyed by question.key)."""
	answers = _parse_answers(answers)

	run = frappe.get_doc("AI Run", run_name)
	if run.owner != frappe.session.user and not frappe.has_permission("AI Run", "write", run):
		frappe.throw(_("Not permitted to resume this run."), frappe.PermissionError)
	if run.status != "Paused":
		frappe.throw(
			_("Only Paused runs can be resumed (this run is {0}).").format(run.status),
			title=_("Cannot Resume"),
		)
	if not run.messages:
		frappe.throw(_("This run has no transcript to resume from."))

	agent = _rebuild_agent(run)
	messages = json.loads(run.messages)
	try:
		result = agent.resume(messages, answers)
	except Exception as e:
		run.mark_failed(str(e))
		raise
	run.apply_result(result)
	return _summarize(run)


def _rebuild_agent(run: AIRun):
	if run.agent:
		return frappe.get_doc("AI Agent", run.agent).assemble()
	from frappe.ai.assistant import build_assistant

	return build_assistant()


def _parse_answers(answers: Any) -> dict[str, Any]:
	if isinstance(answers, str):
		try:
			answers = json.loads(answers)
		except (TypeError, ValueError):
			frappe.throw(_("Answers must be a JSON object."), title=_("Invalid Answers"))
	if not isinstance(answers, dict):
		frappe.throw(_("Answers must be a JSON object."), title=_("Invalid Answers"))
	return answers


def _summarize(run: AIRun) -> dict[str, Any]:
	payload: dict[str, Any] = {
		"name": run.name,
		"status": run.status,
		"iterations": run.iterations,
	}
	if run.status == "Completed":
		payload["output"] = run.output
	elif run.status == "Paused":
		payload["questions"] = json.loads(run.questions) if run.questions else []
	elif run.status == "Failed":
		payload["error"] = run.error
	return payload
