# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
from collections.abc import Generator, Iterable
from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING, Any

import frappe
from frappe import _
from werkzeug.wrappers import Response

if TYPE_CHECKING:
	from flow.flow.doctype.flow_run.flow_run import FlowRun
	from flow.lib.agent import Event


@frappe.whitelist()
def start_run(
	input: str,
	agent: str | None = None,
	session: str | None = None,
	model: str | None = None,
	attachments: list[str] | str | None = None,
	stream: bool | str = False,
) -> dict[str, Any] | Response:
	"""Start a new turn. Creates a session if none is given. `attachments` are uploaded File
	names whose text is injected into this turn. With `stream=True`, returns SSE."""
	if not isinstance(input, str) or not input.strip():
		frappe.throw(_("Input is required."), title=_("Invalid Input"))

	from flow.lib.session import load_session, new_session

	stream = _is_truthy(stream)
	files = _parse_attachments(attachments)
	convo = load_session(session, agent=agent, model=model) if session else new_session(agent, model=model)
	out = convo.chat(input, attachments=files, stream=stream)
	return _sse_response(out) if stream else _summarize(out)


@frappe.whitelist()
def resume_run(
	run_name: str, answers: dict[str, Any] | str, stream: bool | str = False
) -> dict[str, Any] | Response:
	"""Resume a Paused run. `answers` maps each question.key to the user's answer. With `stream=True`, returns SSE."""
	from flow.lib.session import assert_run_owner, load_session

	parsed_answers = _parse_answers(answers)
	stream = _is_truthy(stream)

	run = frappe.get_doc("Flow Run", run_name)
	assert_run_owner(run)
	if run.status != "Paused":
		frappe.throw(
			_("Only Paused runs can be resumed (this run is {0}).").format(run.status),
			title=_("Cannot Resume"),
		)

	out = load_session(run.session).resume(parsed_answers, stream=stream)
	return _sse_response(out) if stream else _summarize(out)


@frappe.whitelist()
def stop_run(run_name: str) -> dict[str, str]:
	"""Stop a run at the user's request: terminate a Paused run so the agent won't continue,
	or finalize a Running one whose SSE stream the client has aborted."""
	from flow.lib.session import assert_run_owner

	if not isinstance(run_name, str) or not run_name.strip():
		frappe.throw(_("Run is required."), title=_("Invalid Run"))

	run = frappe.get_doc("Flow Run", run_name.strip())
	assert_run_owner(run)
	if run.status not in ("Completed", "Failed"):
		run.mark_failed("Stopped by user.")
	return {"status": run.status}


@frappe.whitelist()
def recover_session(session: str) -> dict[str, int]:
	"""Fail any Running run on session (re)load. The client that owned the stream is
	gone, so the run is abandoned; clearing it here unblocks the next turn instead of
	waiting for the stale-run timeout on the next send."""
	if not isinstance(session, str) or not session.strip():
		frappe.throw(_("Session is required."), title=_("Invalid Session"))

	from flow.lib.session import _assert_session_owner

	doc = frappe.get_doc("Flow Session", session.strip())
	_assert_session_owner(doc)

	abandoned = frappe.get_all("Flow Run", filters={"session": doc.name, "status": "Running"}, pluck="name")
	for name in abandoned:
		frappe.db.set_value(
			"Flow Run",
			name,
			{"status": "Failed", "error": "Run abandoned: stream ended without completing."},
		)
	return {"recovered": len(abandoned)}


FEEDBACK_COMMENT_LIMIT = 500


@frappe.whitelist()
def submit_feedback(run_name: str, rating: str, comment: str | None = None) -> dict[str, Any]:
	"""Record thumbs feedback on a finished run, or clear it with rating "None". A
	thumbs-down comment is stored as shared agent memory when the agent has memory
	enabled (a no-op otherwise). Clearing the rating leaves any saved memory intact."""
	from flow.lib.session import assert_run_owner
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
	if run.status not in ("Completed", "Failed"):
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
def get_agent_tools(agent: str) -> dict[str, bool]:
	"""Map an agent's tool slugs to whether each needs confirmation, so the panel can
	classify tool calls (approval vs. inline)"""
	if not isinstance(agent, str) or not agent.strip():
		return {}

	doc = frappe.get_doc("Flow Agent", agent.strip())
	frappe.has_permission("Flow Agent", "read", doc.name, throw=True)

	tool_names = [row.tool for row in doc.tools]
	if not tool_names:
		return {}
	rows = frappe.get_all(
		"Flow Tool", filters={"name": ["in", tool_names]}, fields=["slug", "requires_confirmation"]
	)
	return {row.slug: bool(row.requires_confirmation) for row in rows}


@frappe.whitelist()
def attach_file(file: str) -> dict[str, Any]:
	"""Validate and extract an uploaded File for use as a chat attachment. Errors
	(unsupported type, unreadable, not owned) surface here, at upload time. The
	extracted text is staged in cache; the attachment row is written on send."""
	if not isinstance(file, str) or not file.strip():
		frappe.throw(_("File is required."), title=_("Invalid Attachment"))

	from flow.flow.doctype.flow_session_attachment.flow_session_attachment import stage_attachment

	return stage_attachment(file.strip())


def _sse_response(events: Iterable[Event]) -> Response:
	"""Wrap an event iterable as an SSE HTTP response."""

	def body() -> Generator[bytes]:
		for event in events:
			yield _format_sse(event)

	return Response(
		body(),
		mimetype="text/event-stream",
		headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
	)


def _format_sse(event: Event) -> bytes:
	payload = _event_to_dict(event)
	return f"event: {payload['type']}\ndata: {json.dumps(payload, default=str)}\n\n".encode()


def _event_to_dict(event: Event) -> dict[str, Any]:
	from flow.flow.doctype.flow_run.flow_run import Error, RunStarted
	from flow.lib.agent import Done, TextChunk, ToolEnded, ToolStarted

	if isinstance(event, TextChunk):
		return {"type": "text", "delta": event.text}
	if isinstance(event, ToolStarted):
		return {"type": "tool_started", "id": event.id, "name": event.name, "arguments": event.arguments}
	if isinstance(event, ToolEnded):
		return {"type": "tool_ended", "id": event.id, "name": event.name, "result": event.result}
	if isinstance(event, RunStarted):
		return {"type": "run_started", "name": event.name, "session": event.session}
	if isinstance(event, Error):
		return {"type": "error", "message": event.message}
	if isinstance(event, Done):
		result = event.result
		payload: dict[str, Any] = {
			"type": "done",
			"status": "Paused" if result.paused else "Completed",
			"iterations": result.iterations,
			"output": result.output,
			"usage": result.usage,
		}
		if result.paused:
			payload["questions"] = [asdict(q) for q in result.questions]
		return payload
	if is_dataclass(event):
		return {"type": type(event).__name__.lower(), **asdict(event)}
	raise TypeError(f"Unknown event type: {type(event).__name__}")


def _is_truthy(value: Any) -> bool:
	if isinstance(value, bool):
		return value
	if isinstance(value, int | float):
		return bool(value)
	if isinstance(value, str):
		return value.strip().lower() in {"1", "true", "yes", "on"}
	return bool(value)


def _parse_attachments(value: Any) -> list[str]:
	"""Normalize the attachments argument (a list, a JSON-array string, or empty) to file names."""
	if not value:
		return []
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except (TypeError, ValueError):
			frappe.throw(_("Attachments must be a JSON array of file ids."), title=_("Invalid Attachments"))
	if not isinstance(value, list):
		frappe.throw(_("Attachments must be a list of file ids."), title=_("Invalid Attachments"))
	files: list[str] = []
	for file in value:
		if not isinstance(file, str) or not file.strip():
			frappe.throw(_("Each attachment must be a file id."), title=_("Invalid Attachments"))
		files.append(file.strip())
	return files


def _parse_answers(answers: Any) -> dict[str, Any]:
	if isinstance(answers, str):
		try:
			answers = json.loads(answers)
		except (TypeError, ValueError):
			frappe.throw(_("Answers must be a JSON object."), title=_("Invalid Answers"))
	if not isinstance(answers, dict):
		frappe.throw(_("Answers must be a JSON object."), title=_("Invalid Answers"))
	return answers


def _summarize(run: FlowRun) -> dict[str, Any]:
	payload: dict[str, Any] = {
		"name": run.name,
		"session": run.session,
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
