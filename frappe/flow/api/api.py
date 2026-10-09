# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""The HTTP interface for the /flow page and other clients: thin wrappers over the Flow
Session doc methods, each checking the doctype permission it needs. Nothing here waits for a run."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import frappe
from frappe import _
from frappe.utils import cint

from flow.lib.session import new_session, sync_with_retry

if TYPE_CHECKING:
	from flow.flow.doctype.flow_session.flow_session import FlowSession

FEEDBACK_COMMENT_LIMIT = 500
TITLE_LIMIT = 140
LIST_LIMIT = 100
RUN_FIELDS = ["name", "daemon_run_id", "status", "error", "feedback_rating", "feedback_comment"]
REASONING_EFFORTS = ("off", "minimal", "low", "medium", "high", "xhigh", "max")
# What the /flow page's settings manage; boot reports the caller's rights on each.
SETTINGS_DOCTYPES = (
	"Flow Provider",
	"Flow Model",
	"Flow Agent",
	"Flow Skill",
	"Flow Tool",
	"Flow Trigger",
	"Flow Knowledge Base",
	"Flow Knowledge Source",
	"Flow Knowledge Settings",
	"Flow Agent Memory",
)


@frappe.whitelist()
def boot() -> dict[str, Any]:
	"""What a client needs before its first call: agents and models to pick from, the
	default agent, the file types it may attach, who is signed in and what they may manage."""
	frappe.has_permission("Flow Session", "read", throw=True)
	from flow.assistant.assistant import ASSISTANT_AGENT_TITLE
	from flow.knowledge.extract import FILE_EXTENSIONS

	agents = frappe.get_list("Flow Agent", filters={"enabled": 1}, fields=["name", "title"], order_by="title")
	models = frappe.get_list(
		"Flow Model",
		filters={"enabled": 1},
		fields=["name", "title", "model_id", "provider", "context_window"],
		order_by="title",
	)
	return {
		"agents": agents,
		"default_agent": next((a.name for a in agents if a.name == ASSISTANT_AGENT_TITLE), None),
		"models": models,
		"file_types": sorted(FILE_EXTENSIONS),
		"user": frappe.db.get_value(
			"User", frappe.session.user, ["name", "full_name", "user_image"], as_dict=True
		),
		"permissions": {
			doctype: [
				ptype
				for ptype in ("read", "write", "create", "delete")
				if frappe.has_permission(doctype, ptype)
			]
			for doctype in SETTINGS_DOCTYPES
		},
	}


@frappe.whitelist()
def create_session(
	agent: str | None = None,
	model: str | None = None,
	title: str | None = None,
	auto_approve: bool | int | str = False,
) -> dict[str, Any]:
	"""Start a session with `agent` (the Assistant by default)."""
	frappe.has_permission("Flow Session", "create", throw=True)
	doc = new_session(
		agent or None,
		model=model or None,
		title=(title or "").strip() or None,
		auto_approve=cint(auto_approve),
	)
	return _session_payload(doc)


@frappe.whitelist()
def session(session: str) -> dict[str, Any]:
	"""A session with its runs. One that still has an open run is synced first, which
	repairs a terminal event the client missed; a settled one needs no server call.
	Opening never calls on_complete; the flow server's run-end report does."""
	doc = _load_session(session, "read")
	if frappe.db.exists("Flow Run", {"session": doc.name, "status": ("in", ("Running", "Paused"))}):
		sync_with_retry(doc)
	return _session_payload(doc)


@frappe.whitelist()
def list_sessions(
	query: str | None = None, limit: int | str = 20, before: str | None = None
) -> list[dict[str, Any]]:
	"""The user's own conversations, newest first; `query` narrows them by title, `before`
	(the `modified` of the last row shown) continues past it."""
	frappe.has_permission("Flow Session", "read", throw=True)
	filters: dict[str, Any] = {"owner": frappe.session.user, "source": ("!=", "Trigger")}
	if query and query.strip():
		filters["title"] = ("like", f"%{_escape_like(query.strip())}%")
	if before:
		filters["modified"] = ("<", before)
	rows = frappe.get_all(
		"Flow Session",
		filters=filters,
		fields=["name", "title", "agent", "model", "modified"],
		order_by="modified desc",
		limit=min(cint(limit) or 20, LIST_LIMIT),
	)
	# the model in force, as `session` reports it: the chat's own pick, else its agent's
	for row in rows:
		if not row.model and row.agent:
			row.model = frappe.get_cached_value("Flow Agent", row.agent, "model")
	return rows


@frappe.whitelist()
def skills(session: str | None = None, agent: str | None = None) -> dict[str, Any]:
	"""The skills a user may start by typing /skill:<name>: those of `session`'s agent, or of
	`agent` for a chat not started yet."""
	if session:
		agent = _load_session(session, "read").agent
	elif isinstance(agent, str) and agent.strip():
		agent = agent.strip()
		frappe.has_permission("Flow Agent", "read", agent, throw=True)
	else:
		frappe.throw(_("Session or agent is required."), title=_("Invalid Request"))
	return {
		"skills": [
			{"name": row["command"], "description": row["description"]}
			for row in frappe.get_doc("Flow Agent", agent).invocable_skills()
		]
	}


@frappe.whitelist()
def run(session: str, message: str, attachments: list[str] | str | None = None) -> dict[str, Any]:
	"""Start a turn and answer at once: "started" with its new run, or "steered" with the
	active run the message joined. `attachments` are File names staged with attach_file."""
	if not isinstance(message, str) or not message.strip():
		frappe.throw(_("Message is required."), title=_("Invalid Message"))
	doc = _load_session(session, "write")
	# a queued message goes out the moment a run ends, racing that run's own syncs
	sync_with_retry(doc)
	active = frappe.db.get_value(
		"Flow Run", {"session": doc.name, "status": "Running"}, "name", order_by="creation desc"
	)
	run = doc.chat(message, attachments=_parse_attachments(attachments))
	return {"run": run.name, "status": "steered" if run.name == active else "started"}


@frappe.whitelist()
def resume(
	session: str, answers: dict[str, Any] | str, approval_seq: int | str | None = None
) -> dict[str, Any]:
	"""Answer the paused run's approval batch, keyed by tool call id, or a sub-agent's batch
	named by `approval_seq`."""
	doc = _load_session(session, "write")
	run = doc.resume(_parse_answers(answers), approval_seq=cint(approval_seq) or None)
	return {"run": run.name, "status": "started"}


@frappe.whitelist()
def abort(session: str) -> dict[str, str]:
	return {"status": _load_session(session, "write").abort()}


@frappe.whitelist()
def cancel_pending(session: str) -> dict[str, str]:
	return {"status": _load_session(session, "write").cancel_pending()}


@frappe.whitelist()
def entries(session: str, since: int | str = 0, path: str = "active") -> dict[str, Any]:
	if path not in ("active", "all"):
		frappe.throw(_("Path must be active or all."), title=_("Invalid Path"))
	return _load_session(session, "read").entries(since=cint(since), path=path)


@frappe.whitelist()
def set_model(session: str, model: str, reasoning_effort: str | None = None) -> dict[str, Any]:
	"""Switch the session's model; `reasoning_effort` sets its thinking level, empty for the default."""
	if not isinstance(model, str) or not model.strip():
		frappe.throw(_("Model is required."), title=_("Invalid Model"))
	effort = (reasoning_effort or "").strip() or None
	if effort is not None and effort not in REASONING_EFFORTS:
		frappe.throw(
			_("Reasoning effort must be one of {0}.").format(", ".join(REASONING_EFFORTS)),
			title=_("Invalid Reasoning Effort"),
		)
	_load_session(session, "write").set_model(model.strip(), reasoning_effort=effort)
	return {
		"model": model.strip(),
		"reasoning_effort": effort,
	}


@frappe.whitelist()
def set_title(session: str, title: str) -> dict[str, str]:
	title = (title or "").strip()[:TITLE_LIMIT]
	if not title:
		frappe.throw(_("Title is required."), title=_("Invalid Title"))
	_load_session(session, "write").set_title(title)
	return {"title": title}


@frappe.whitelist()
def set_auto_approve(session: str, auto_approve: bool | int | str) -> dict[str, bool]:
	"""Whether confirmation tools run unattended; Trigger sessions cannot turn it off."""
	flag = bool(cint(auto_approve))
	_load_session(session, "write").set_auto_approve(flag)
	return {"auto_approve": flag}


@frappe.whitelist()
def delete_session(session: str) -> dict[str, str]:
	_load_session(session, "delete").delete()
	return {"status": "deleted"}


@frappe.whitelist()
def sync_session(session: str) -> dict[str, Any]:
	"""Record the flow server's log into this session after a terminal event, or when a
	client reconnects; never called on a schedule."""
	doc = _load_session(session, "read")
	sync_with_retry(doc)
	return _session_payload(doc)


@frappe.whitelist()
def submit_feedback(run_name: str, rating: str, comment: str | None = None) -> dict[str, Any]:
	"""Record thumbs feedback on a finished run, or clear it with rating "None". A
	thumbs-down comment is stored as shared agent memory when the agent has memory
	enabled (a no-op otherwise); clearing the rating drops that memory again."""
	from flow.memory.memory import forget_feedback_memory, save_feedback_memory

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
	frappe.has_permission("Flow Run", "read", run, throw=True)
	if run.owner != frappe.session.user:
		frappe.has_permission("Flow Run", "write", run, throw=True)
	if run.status not in ("Completed", "Denied", "Failed"):
		frappe.throw(
			_("Feedback applies to finished runs only (this run is {0}).").format(run.status),
			title=_("Run Not Finished"),
		)

	if rating == "None":
		forgotten = forget_feedback_memory(run)
		run.db_set({"feedback_rating": "", "feedback_comment": None})
		return {"rating": None, "forgotten": forgotten} if forgotten else {"rating": None}

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

	frappe.has_permission("Flow Session", "create", throw=True)
	from flow.flow.doctype.flow_session_attachment.flow_session_attachment import stage_attachment

	return stage_attachment(file.strip())


@frappe.whitelist()
def cleanup_attachments(
	session: str | None = None, attachments: list[str] | str | None = None
) -> dict[str, list[str]]:
	"""Discard staged uploads that no accepted turn references."""
	if session:
		_load_session(session, "write")
	else:
		frappe.has_permission("Flow Session", "create", throw=True)
	removed = []
	for file in _parse_attachments(attachments):
		row = frappe.db.get_value("File", file, ["owner", "attached_to_doctype"], as_dict=True)
		if not row or row.owner != frappe.session.user or row.attached_to_doctype:
			continue
		if frappe.db.exists("Flow Session Attachment", {"file": file}):
			continue
		frappe.delete_doc("File", file, ignore_permissions=True)
		removed.append(file)
	return {"removed": removed}


def _load_session(session: str, ptype: str) -> FlowSession:
	if not isinstance(session, str) or not session.strip():
		frappe.throw(_("Session is required."), title=_("Invalid Session"))
	doc = frappe.get_doc("Flow Session", session.strip())
	frappe.has_permission("Flow Session", ptype, doc, throw=True)
	return doc


def _session_payload(doc: FlowSession) -> dict[str, Any]:
	model = doc.model or frappe.get_cached_value("Flow Agent", doc.agent, "model")
	return {
		"name": doc.name,
		"title": doc.title,
		"agent": doc.agent,
		"model": model,
		"source": doc.source,
		"auto_approve": bool(doc.auto_approve),
		"read_only": not frappe.has_permission("Flow Session", "write", doc),
		"runs": frappe.get_all(
			"Flow Run", filters={"session": doc.name}, fields=RUN_FIELDS, order_by="creation asc"
		),
	}


def _escape_like(text: str) -> str:
	return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _parse_attachments(attachments: Any) -> list[str]:
	if attachments in (None, ""):
		return []
	if isinstance(attachments, str):
		try:
			attachments = json.loads(attachments)
		except ValueError:
			attachments = None
	if not isinstance(attachments, list) or not all(isinstance(f, str) and f.strip() for f in attachments):
		frappe.throw(_("Attachments must be a list of File names."), title=_("Invalid Attachments"))
	return [f.strip() for f in attachments]


def _parse_answers(answers: Any) -> dict[str, Any]:
	if isinstance(answers, str):
		try:
			answers = json.loads(answers)
		except ValueError:
			answers = None
	if not isinstance(answers, dict):
		frappe.throw(_("Answers must be a JSON object."), title=_("Invalid Answers"))
	return answers
