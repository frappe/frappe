# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""The HTTP interface for the /flow page and other clients: thin, owner-checked wrappers
over the Flow Session doc methods. Nothing here waits for a run."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import frappe
from frappe import _
from frappe.utils import cint

from flow.lib.session import _assert_session_owner, assert_run_owner, new_session

if TYPE_CHECKING:
	from flow.flow.doctype.flow_session.flow_session import FlowSession

FEEDBACK_COMMENT_LIMIT = 500
TITLE_LIMIT = 140
LIST_LIMIT = 100
RUN_FIELDS = ["name", "daemon_run_id", "status", "error", "feedback_rating", "feedback_comment"]


@frappe.whitelist()
def boot() -> dict[str, Any]:
	"""What a client needs before its first call: agents and models to pick from, the
	default agent, and the file types it may attach."""
	from flow.assistant.assistant import ASSISTANT_AGENT_TITLE
	from flow.knowledge.extract import FILE_EXTENSIONS

	fields = ["name", "title"]
	agents = frappe.get_list("Flow Agent", filters={"enabled": 1}, fields=fields, order_by="title")
	return {
		"agents": agents,
		"default_agent": next((a.name for a in agents if a.name == ASSISTANT_AGENT_TITLE), None),
		"models": frappe.get_list("Flow Model", filters={"enabled": 1}, fields=fields, order_by="title"),
		"file_types": sorted(FILE_EXTENSIONS),
	}


@frappe.whitelist()
def create_session(
	agent: str | None = None,
	model: str | None = None,
	title: str | None = None,
	auto_approve: bool | int | str = False,
) -> dict[str, Any]:
	"""Start a session with `agent` (the Assistant by default)."""
	doc = new_session(
		agent or None, model=model or None, title=(title or "").strip() or None, auto_approve=cint(auto_approve)
	)
	return _session_payload(doc)


@frappe.whitelist()
def session(session: str) -> dict[str, Any]:
	"""A session with its runs. One that still has an open run is synced first, which
	repairs a terminal event the client missed; a settled one needs no server call."""
	doc = _owned_session(session)
	if frappe.db.exists("Flow Run", {"session": doc.name, "status": ("in", ("Running", "Paused"))}):
		doc.sync()
	return _session_payload(doc)


@frappe.whitelist()
def list_sessions(query: str | None = None, limit: int | str = 20) -> list[dict[str, Any]]:
	"""The user's own conversations, newest first; `query` narrows them by title."""
	filters: dict[str, Any] = {"owner": frappe.session.user, "source": ("!=", "Trigger")}
	if query and query.strip():
		filters["title"] = ("like", f"%{_escape_like(query.strip())}%")
	return frappe.get_all(
		"Flow Session",
		filters=filters,
		fields=["name", "title", "agent", "model", "modified"],
		order_by="modified desc",
		limit=min(cint(limit) or 20, LIST_LIMIT),
	)


@frappe.whitelist()
def run(session: str, message: str) -> dict[str, Any]:
	"""Start a turn and answer at once: "started" with its new run, or "steered" with the
	active run the message joined."""
	if not isinstance(message, str) or not message.strip():
		frappe.throw(_("Message is required."), title=_("Invalid Message"))
	doc = _owned_session(session)
	active = frappe.db.get_value(
		"Flow Run", {"session": doc.name, "status": "Running"}, "name", order_by="creation desc"
	)
	run = doc.chat(message)
	return {"run": run.name, "status": "steered" if run.name == active else "started"}


@frappe.whitelist()
def resume(session: str, answers: dict[str, Any] | str) -> dict[str, Any]:
	"""Answer the paused run's approval batch, keyed by tool call id."""
	run = _owned_session(session).resume(_parse_answers(answers))
	return {"run": run.name, "status": "started"}


@frappe.whitelist()
def abort(session: str) -> dict[str, str]:
	return {"status": _owned_session(session).abort()}


@frappe.whitelist()
def cancel_pending(session: str) -> dict[str, str]:
	return {"status": _owned_session(session).cancel_pending()}


@frappe.whitelist()
def entries(session: str, since: int | str = 0, path: str = "active") -> dict[str, Any]:
	if path not in ("active", "all"):
		frappe.throw(_("Path must be active or all."), title=_("Invalid Path"))
	return _owned_session(session).entries(since=cint(since), path=path)


@frappe.whitelist()
def set_model(session: str, model: str) -> dict[str, str]:
	if not isinstance(model, str) or not model.strip():
		frappe.throw(_("Model is required."), title=_("Invalid Model"))
	_owned_session(session).set_model(model.strip())
	return {"model": model.strip()}


@frappe.whitelist()
def set_title(session: str, title: str) -> dict[str, str]:
	title = (title or "").strip()[:TITLE_LIMIT]
	if not title:
		frappe.throw(_("Title is required."), title=_("Invalid Title"))
	_owned_session(session).set_title(title)
	return {"title": title}


@frappe.whitelist()
def set_auto_approve(session: str, auto_approve: bool | int | str) -> dict[str, bool]:
	"""Whether confirmation tools run unattended; Trigger sessions cannot turn it off."""
	flag = bool(cint(auto_approve))
	_owned_session(session).set_auto_approve(flag)
	return {"auto_approve": flag}


@frappe.whitelist()
def delete_session(session: str) -> dict[str, str]:
	_owned_session(session).delete(ignore_permissions=True)
	return {"status": "deleted"}


@frappe.whitelist()
def sync_session(session: str) -> dict[str, Any]:
	"""Record the flow server's log into this session after a terminal event, or when a
	client reconnects; never called on a schedule."""
	doc = _owned_session(session)
	doc.sync()
	return _session_payload(doc)


@frappe.whitelist()
def submit_feedback(run_name: str, rating: str, comment: str | None = None) -> dict[str, Any]:
	"""Record thumbs feedback on a finished run, or clear it with rating "None". A
	thumbs-down comment is stored as shared agent memory when the agent has memory
	enabled (a no-op otherwise). Clearing the rating leaves any saved memory intact."""
	from flow.memory.memory import save_feedback_memory

	if not isinstance(run_name, str) or not run_name.strip():
		frappe.throw(_("Run is required."), title=_("Invalid Run"))
	if rating not in ("Up", "Down", "None"):
		frappe.throw(_("Rating must be Up, Down, or None."), title=_("Invalid Rating"))
	comment = (comment or "").strip()
	if len(comment) > FEEDBACK_COMMENT_LIMIT:
		frappe.throw(
			_("Keep feedback under {0} characters.").format(FEEDBACK_COMMENT_LIMIT),
			title=_("Feedback Too Long"),
		)

	run = frappe.get_doc("Flow Run", run_name.strip())
	assert_run_owner(run)
	if run.status not in ("Completed", "Denied", "Failed"):
		frappe.throw(
			_("Feedback applies to finished runs only (this run is {0}).").format(run.status),
			title=_("Run Not Finished"),
		)

	if rating == "None":
		run.db_set({"feedback_rating": "", "feedback_comment": None})
		return {"rating": None}

	memory = save_feedback_memory(run, comment) if rating == "Down" and comment else None
	run.db_set({"feedback_rating": rating, "feedback_comment": comment or None})

	result: dict[str, Any] = {"rating": rating}
	if memory:
		result["memory"] = memory
	return result


@frappe.whitelist()
def attach_file(file: str) -> dict[str, Any]:
	"""Validate and extract an uploaded File for use as a chat attachment. Errors
	(unsupported type, unreadable, not owned) surface here, at upload time. The
	extracted text is staged in cache; the attachment row is written on send."""
	if not isinstance(file, str) or not file.strip():
		frappe.throw(_("File is required."), title=_("Invalid Attachment"))

	from flow.flow.doctype.flow_session_attachment.flow_session_attachment import stage_attachment

	return stage_attachment(file.strip())


def _owned_session(session: str) -> FlowSession:
	if not isinstance(session, str) or not session.strip():
		frappe.throw(_("Session is required."), title=_("Invalid Session"))
	doc = frappe.get_doc("Flow Session", session.strip())
	_assert_session_owner(doc)
	return doc


def _session_payload(doc: FlowSession) -> dict[str, Any]:
	return {
		"name": doc.name,
		"title": doc.title,
		"agent": doc.agent,
		"model": doc.model,
		"source": doc.source,
		"auto_approve": bool(doc.auto_approve),
		"runs": frappe.get_all(
			"Flow Run", filters={"session": doc.name}, fields=RUN_FIELDS, order_by="creation asc"
		),
	}


def _escape_like(text: str) -> str:
	return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _parse_answers(answers: Any) -> dict[str, Any]:
	if isinstance(answers, str):
		try:
			answers = json.loads(answers)
		except ValueError:
			answers = None
	if not isinstance(answers, dict):
		frappe.throw(_("Answers must be a JSON object."), title=_("Invalid Answers"))
	return answers
