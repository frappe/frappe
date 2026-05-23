# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

import frappe
from frappe import _
from frappe.model.document import Document

if TYPE_CHECKING:
	from frappe.ai.agent import RunResult

JSON_FIELDS = ("messages", "tool_calls", "questions", "usage", "config_snapshot")


class AIRun(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		agent: DF.Data | None
		config_snapshot: DF.JSON | None
		error: DF.LongText | None
		input: DF.LongText | None
		iterations: DF.Int
		messages: DF.JSON | None
		output: DF.LongText | None
		questions: DF.JSON | None
		source: DF.Literal["Manual", "Trigger", "Planner"]
		status: DF.Literal["Running", "Paused", "Completed", "Failed"]
		tool_calls: DF.JSON | None
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
		"""Update this row to reflect a (re-)executed Agent run."""
		self.status = _status_from_result(result)
		self.iterations = result.iterations
		self.output = result.output
		self.messages = _dump_json(result.messages)
		self.tool_calls = _dump_json([asdict(call) for call in result.tool_calls])
		self.questions = _dump_json([asdict(q) for q in result.questions]) if result.paused else None
		self.usage = _dump_json(result.usage)
		if self.status != "Failed":
			self.error = None
		self.save(ignore_permissions=True)

	def mark_failed(self, error: str) -> None:
		"""Mark a run as failed with the given error message."""
		self.status = "Failed"
		self.error = str(error)[:5000]
		self.save(ignore_permissions=True)


def create_run(
	*,
	source: str,
	input: str | None,
	agent: str | None = None,
	config_snapshot: dict[str, Any] | None = None,
) -> AIRun:
	"""Create a new AI Run row in the Running state."""
	doc = frappe.get_doc(
		{
			"doctype": "AI Run",
			"source": source,
			"input": input,
			"agent": agent,
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
	agent: str | None = None,
	config_snapshot: dict[str, Any] | None = None,
) -> AIRun:
	"""Convenience: create a row and immediately apply a finished RunResult."""
	doc = create_run(source=source, input=input, agent=agent, config_snapshot=config_snapshot)
	doc.apply_result(result)
	return doc


def _status_from_result(result: RunResult) -> str:
	if result.paused:
		return "Paused"
	return "Completed"


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
