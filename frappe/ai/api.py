# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
from collections.abc import Generator, Iterable
from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING, Any

from werkzeug.wrappers import Response

import frappe
from frappe import _

if TYPE_CHECKING:
	from frappe.ai.agent import Event
	from frappe.ai.doctype.ai_run.ai_run import AIRun


@frappe.whitelist()
def start_run(
	input: str,
	agent: str | None = None,
	session: str | None = None,
	model: str | None = None,
	stream: bool | str = False,
) -> dict[str, Any] | Response:
	"""Start a new turn. Creates a session if none is given. With `stream=True`, returns SSE."""
	if not isinstance(input, str) or not input.strip():
		frappe.throw(_("Input is required."), title=_("Invalid Input"))

	from frappe.ai import runner

	stream = _is_truthy(stream)
	out = runner.start(input=input, agent=agent, session=session, model=model, stream=stream)
	return _sse_response(out) if stream else _summarize(out)


@frappe.whitelist()
def resume_run(
	run_name: str, answers: dict[str, Any] | str, stream: bool | str = False
) -> dict[str, Any] | Response:
	"""Resume a Paused run. `answers` maps each question.key to the user's answer. With `stream=True`, returns SSE."""
	from frappe.ai import runner

	parsed_answers = _parse_answers(answers)
	stream = _is_truthy(stream)
	out = runner.resume(run_name=run_name, answers=parsed_answers, stream=stream)
	return _sse_response(out) if stream else _summarize(out)


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
	from frappe.ai.agent import Done, TextChunk, ToolEnded, ToolStarted
	from frappe.ai.doctype.ai_run.ai_run import Error, RunStarted

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
