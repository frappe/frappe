# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
from collections.abc import Callable, Generator
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

import frappe
from frappe import _
from frappe.model.document import Document

if TYPE_CHECKING:
	from frappe.ai.agent import Event, RunResult

JSON_FIELDS = ("tool_calls", "questions", "usage", "config_snapshot")


@dataclass
class RunStarted:
	"""Streaming event: announces this run's persistent name as the first frame."""

	name: str


@dataclass
class Error:
	"""Streaming event: an exception ended the stream; the message has been persisted as the run error."""

	message: str


class AIRun(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		config_snapshot: DF.JSON | None
		error: DF.LongText | None
		input: DF.LongText | None
		iterations: DF.Int
		output: DF.LongText | None
		questions: DF.JSON | None
		session: DF.Link
		source: DF.Literal["Manual", "Trigger"]
		status: DF.Literal["Running", "Paused", "Completed", "Failed"]
		tool_calls: DF.JSON | None
		trigger: DF.Link | None
		usage: DF.JSON | None
	# end: auto-generated types

	def validate(self):
		self._validate_json_fields()
		self._validate_status_invariants()

	def _validate_json_fields(self):
		for fieldname in JSON_FIELDS:
			value = self.get(fieldname)
			if value in (None, ""):
				continue
			if not isinstance(value, str):
				continue
			try:
				json.loads(value)
			except (TypeError, ValueError):
				frappe.throw(
					_("{0} must be valid JSON.").format(fieldname),
					title=_("Invalid JSON"),
				)

	def _validate_status_invariants(self):
		if self.status == "Paused" and not _json_has_items(self.questions):
			frappe.throw(_("Paused runs must have at least one pending question."))
		if self.status == "Failed" and not self.error:
			frappe.throw(_("Failed runs must include an error message."))

	def apply_result(self, result: RunResult) -> None:
		"""Update this row to reflect a (re-)executed Agent run. The new messages produced
		by this run are appended to the parent Session's transcript."""
		self.status = _status_from_result(result)
		self.iterations = result.iterations
		self.output = result.output
		self.tool_calls = _dump_json([asdict(call) for call in result.tool_calls])
		self.questions = _dump_json([asdict(q) for q in result.questions]) if result.paused else None
		self.usage = _dump_json(result.usage)
		if self.status != "Failed":
			self.error = None
		self.save(ignore_permissions=True)

		new_messages = _new_messages_for_session(self.session, result.messages)
		if new_messages:
			session = frappe.get_doc("AI Session", self.session)
			session.append_run_messages(new_messages, run=self.name)

	def mark_failed(self, error: str) -> None:
		"""Mark a run as failed with the given error message."""
		self.status = "Failed"
		self.error = str(error)[:5000]
		self.save(ignore_permissions=True)


def create_run(
	*,
	source: str,
	input: str | None,
	session: str,
	trigger: str | None = None,
	config_snapshot: dict[str, Any] | None = None,
) -> AIRun:
	"""Create a new AI Run row in the Running state. `session` is required — every run
	belongs to an AI Session (which carries the transcript and agent linkage)."""
	doc = frappe.get_doc(
		{
			"doctype": "AI Run",
			"source": source,
			"input": input,
			"trigger": trigger,
			"session": session,
			"config_snapshot": _dump_json(config_snapshot) if config_snapshot else None,
			"status": "Running",
		}
	).insert(ignore_permissions=True)
	return doc


def persist_result(
	result: RunResult,
	*,
	source: str,
	input: str | None,
	session: str,
	trigger: str | None = None,
	config_snapshot: dict[str, Any] | None = None,
) -> AIRun:
	"""Convenience: create a row and immediately apply a finished RunResult."""
	doc = create_run(
		source=source,
		input=input,
		session=session,
		trigger=trigger,
		config_snapshot=config_snapshot,
	)
	doc.apply_result(result)
	return doc


def stream_with_persistence(
	make_events: Callable[[], Generator[Event]],
	run: AIRun,
) -> Generator[Event | RunStarted | Error]:
	"""Wrap an agent event stream with run lifecycle: announce RunStarted, persist on
	Done, mark Failed + emit Error if the stream raises.

	Commits explicitly: streamed responses are iterated by WSGI *after* the request
	handler returns, so the framework's end-of-request commit has already fired by
	the time persistence happens here.
	"""
	from frappe.ai.agent import Done

	yield RunStarted(name=run.name)

	final_result: RunResult | None = None
	persisted = False
	try:
		for event in make_events():
			if isinstance(event, Done):
				final_result = event.result
			yield event

		if final_result is not None:
			run.apply_result(final_result)
			persisted = True
			if not frappe.flags.in_test:
				frappe.db.commit()
	except Exception as e:
		persisted = True
		run.mark_failed(str(e))
		if not frappe.flags.in_test:
			frappe.db.commit()
		yield Error(message=str(e))
	finally:
		# Stream cut short (e.g. client disconnect raises GeneratorExit) before
		# we persisted — record the run as failed so it doesn't sit in "Running".
		if not persisted:
			try:
				run.mark_failed("Stream interrupted")
				if not frappe.flags.in_test:
					frappe.db.commit()
			except Exception:
				pass


def _status_from_result(result: RunResult) -> str:
	if result.paused:
		return "Paused"
	return "Completed"


def _new_messages_for_session(session: str, full_transcript: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""Return new messages produced by this run, excluding the session's prior history."""
	existing = frappe.db.count("AI Session Message", {"parent": session})
	return list(full_transcript[existing:])


def _dump_json(value: Any) -> str | None:
	if value is None:
		return None
	return json.dumps(value, default=str)


def _json_has_items(value: Any) -> bool:
	if not value:
		return False
	try:
		parsed = json.loads(value) if isinstance(value, str) else value
	except (TypeError, ValueError):
		return False
	return bool(parsed)
