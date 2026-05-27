# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING, Any

import frappe
from frappe import _
from frappe.ai.agent import Agent
from frappe.ai.doctype.ai_run.ai_run import create_run, stream_with_persistence
from frappe.ai.model import Model
from frappe.ai.tools.builtins import ask_user, execute, introspect, query

if TYPE_CHECKING:
	from frappe.ai.agent import Event
	from frappe.ai.doctype.ai_run.ai_run import AIRun

ASSISTANT_NAME = "assistant"

ASSISTANT_INSTRUCTIONS = (
	"You are a Frappe assistant working inside a Frappe site. The user asks you to "
	"read or change data within it.\n\n"
	"Tools:\n"
	"- introspect(doctype): inspect a DocType's fields and your permissions before using it\n"
	"- query(doctype, filters, fields, limit, order_by): read records\n"
	"- execute(code): run Python in a sandbox; use it for writes, emails, and computation\n"
	"- ask_user(prompt, options, multi_select): pause and ask the user a question\n\n"
	"Workflow: introspect → query → ask_user to confirm → execute.\n\n"
	"RULES:\n"
	"1. Before any write, delete, or email you MUST call ask_user() to confirm — "
	"never ask in plain text and never act without confirmation.\n"
	"2. Never end a reply with a question — use ask_user() instead.\n"
	"3. Never invent DocType, field, or record names — verify with introspect or query first.\n"
	"4. If the user wants something recurring, named, or reusable "
	'("an agent that…", "every Friday…", "whenever X happens…") create an AI Agent '
	"row plus an AI Trigger row (DocType Event or Scheduled). Show the exact JSON via "
	"ask_user() before inserting. Do not also perform the action inline.\n"
	"5. If the user wants a one-shot action, confirm via ask_user() and execute() it "
	"directly. Do not create an Agent/Trigger.\n"
	"6. When the task is done, reply in plain text."
)

ASSISTANT_TOOLS = [introspect, query, execute, ask_user]


def build_assistant(*, model: Model | str | None = None) -> Agent:
	"""Build the default in-memory assistant: instructions + the three primitives + ask_user."""
	if model is None:
		model = _default_model_name()
	return Agent(
		model=model,
		name=ASSISTANT_NAME,
		instructions=ASSISTANT_INSTRUCTIONS,
		tools=ASSISTANT_TOOLS,
	)


def run_assistant(
	input: str,
	*,
	model: Model | str | None = None,
	source: str = "Manual",
	stream: bool = False,
) -> AIRun | Generator[Event]:
	"""Run the assistant on `input`, persist the transcript as an AI Run, and return it.

	With `stream=True`, returns a generator of agent Events instead of the AIRun row;
	the run is still created up-front (first event is `RunStarted` with its name) and
	persisted when the stream completes.
	"""
	agent = build_assistant(model=model)
	session = _new_session(input)
	run = create_run(source=source, input=input, session=session, config_snapshot=_snapshot(agent))
	if stream:
		return stream_with_persistence(lambda: agent.run(input, stream=True), run)

	try:
		result = agent.run(input)
	except Exception as e:
		run.mark_failed(str(e))
		raise
	run.apply_result(result)
	return run


def _new_session(input_text: str, agent: str | None = None) -> str:
	from frappe.ai.doctype.ai_session.ai_session import derive_title

	session = frappe.get_doc(
		{
			"doctype": "AI Session",
			"agent": agent,
			"title": derive_title(input_text),
		}
	).insert(ignore_permissions=True)
	return session.name


def _default_model_name() -> str:
	name = frappe.db.get_value("AI Model", {"enabled": 1}, "name")
	if not name:
		frappe.throw(
			_("No enabled AI Model found. Create one in the AI Model list first."),
			title=_("Missing AI Model"),
		)
	return name


def _snapshot(agent: Agent) -> dict[str, Any]:
	return {
		"name": agent.name,
		"instructions": agent.instructions,
		"tools": [t.name for t in agent.tools],
		"max_iterations": agent.max_iterations,
		"model_id": getattr(agent.model, "model_id", None),
	}
