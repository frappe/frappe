# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import frappe
from frappe import _
from frappe.model.document import Document

if TYPE_CHECKING:
	from collections.abc import Generator

	from flow.ai.doctype.ai_run.ai_run import AIRun
	from flow.lib.agent import Event

TITLE_MAX_LENGTH = 80
# A "Running" run older than this is treated as abandoned and no longer blocks the session.
RUNNING_STALE_SECONDS = 300


class AISession(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from flow.ai.doctype.ai_session_attachment.ai_session_attachment import AISessionAttachment
		from flow.ai.doctype.ai_session_message.ai_session_message import AISessionMessage

		agent: DF.Link | None
		attachments: DF.Table[AISessionAttachment]
		messages: DF.Table[AISessionMessage]
		model: DF.Link | None
		title: DF.Data | None
	# end: auto-generated types

	def validate(self):
		self._validate_agent_unchanged()
		self._validate_model_enabled()

	def _validate_model_enabled(self):
		if not self.model:
			return
		if not frappe.db.get_value("AI Model", self.model, "enabled"):
			frappe.throw(
				_("AI Model {0} is disabled.").format(self.model),
				title=_("Disabled Model"),
			)

	def _validate_agent_unchanged(self):
		"""The agent that drives a session is fixed at creation. Subsequent turns must use the same agent."""
		if self.is_new():
			return
		db_agent = frappe.db.get_value("AI Session", self.name, "agent")
		if (db_agent or None) != (self.agent or None):
			frappe.throw(
				_("Cannot change the agent on an existing session."),
				title=_("Agent Locked"),
			)

	@staticmethod
	def clear_old_logs(days=30):
		"""Delete sessions idle for `days`, along with their AI Runs and transcript rows.
		Age is last activity (modified), so an actively-used session is never purged."""
		cutoff = frappe.utils.add_days(frappe.utils.now(), -days)
		sessions = frappe.get_all("AI Session", filters={"modified": ["<", cutoff]}, pluck="name")
		for batch in frappe.utils.create_batch(sessions, 100):
			frappe.db.delete("AI Run", {"session": ["in", batch]})
			frappe.db.delete("AI Session Message", {"parent": ["in", batch]})
			frappe.db.delete("AI Session", {"name": ["in", batch]})

	def transcript(self) -> list[dict[str, Any]]:
		"""Return the conversation history in OpenAI message format."""
		return [_row_to_message(row) for row in self.messages]

	def append_run_messages(self, new_messages: list[dict[str, Any]], run: str) -> None:
		"""Append the messages produced by `run` to this session's transcript.

		`new_messages` should be the delta — only messages this run added — not the
		cumulative history. Each row is tagged with the producing run for traceability.
		"""
		for message in new_messages:
			role = message.get("role")
			tool_calls = message.get("tool_calls")
			self.append(
				"messages",
				{
					"role": role,
					"content": message.get("content"),
					"tool_call_id": message.get("tool_call_id"),
					"tool_calls": json.dumps(tool_calls) if tool_calls else None,
					"run": run,
				},
			)
		self.save(ignore_permissions=True)

	def chat(
		self,
		input: str,
		*,
		attachments: list[str] | None = None,
		source: str = "Manual",
		trigger: str | None = None,
		reference_doctype: str | None = None,
		reference_name: str | None = None,
		stream: bool = False,
	) -> AIRun | Generator[Event]:
		"""Run one turn and persist it as an AI Run. `attachments` are File names whose text
		is injected into this turn's prompt. With `stream=True`, returns an event generator."""
		from flow.ai.doctype.ai_run.ai_run import create_run, stream_with_persistence

		self.reload()
		self._assert_not_blocked()
		attachment_data = self._load_attachments(attachments)
		if not self.title:
			self.db_set("title", derive_title(input))

		run = create_run(
			source=source,
			input=input,
			session=self.name,
			trigger=trigger,
			reference_doctype=reference_doctype,
			reference_name=reference_name,
			config_snapshot=self._snapshot,
		)
		self._persist_turn(input, attachment_data, run.name)
		run_input = self._build_prompt_messages()

		if stream:
			return stream_with_persistence(lambda: self._runtime.run(run_input, stream=True), run)

		try:
			result = self._runtime.run(run_input)
		except Exception as e:
			run.mark_failed(str(e))
			raise
		run.apply_result(result)
		return run

	def _load_attachments(self, attachments: list[str] | None) -> list[dict[str, Any]]:
		"""Validate and extract each attached file (errors surface before the run is created)."""
		from flow.ai.doctype.ai_session_attachment.ai_session_attachment import resolve_attachment

		seen: set[str] = set()
		resolved: list[dict[str, Any]] = []
		for file in attachments or []:
			if file in seen:
				continue
			seen.add(file)
			resolved.append(resolve_attachment(file))
		return resolved

	def _persist_turn(self, input: str, attachment_data: list[dict[str, Any]], run: str) -> None:
		"""Persist this turn's user message (and the system message on the first turn) plus its
		attachment rows before the run executes. Stored ahead of the run so they fall in the
		transcript prefix the run's own message-append skips — the run persists only its output."""
		if not self.messages and self._runtime.instructions:
			self.append("messages", {"role": "system", "content": self._runtime.instructions, "run": run})
		self.append("messages", {"role": "user", "content": input, "run": run})
		for data in attachment_data:
			self.append(
				"attachments",
				{
					"file": data["file"],
					"file_name": data["file_name"],
					"file_size": data["file_size"],
					"extracted_text": data["extracted_text"],
					"run": run,
				},
			)
		self.save(ignore_permissions=True)

	def resume(self, answers: dict[str, Any], *, stream: bool = False) -> AIRun | Generator[Event]:
		"""Resume this session's paused run with the user's answers."""
		from flow.ai.doctype.ai_run.ai_run import stream_with_persistence

		run_name = frappe.db.get_value(
			"AI Run",
			{"session": self.name, "status": "Paused"},
			"name",
			order_by="creation desc",
		)
		if not run_name:
			frappe.throw(_("This session has no paused run to resume."), title=_("Nothing to Resume"))
		run = frappe.get_doc("AI Run", run_name)

		self.reload()
		messages = self._build_prompt_messages()
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

	def _build_prompt_messages(self) -> list[dict[str, Any]]:
		"""Transcript as sent to the model: every user turn's content is augmented with the
		text of the files attached on that turn, so the file stays in context for the whole
		conversation (matching ChatGPT/Claude/Gemini). The augmentation is ephemeral — stored
		messages stay clean (the file text lives only in the attachments child table)."""
		by_run = self._group_attachments_by_run()
		messages: list[dict[str, Any]] = []
		for row in self.messages:
			message = _row_to_message(row)
			if row.role == "user" and row.run in by_run:
				message["content"] = _inject_file_text(message["content"], by_run[row.run])
			messages.append(message)
		return messages

	def _group_attachments_by_run(self) -> dict[str, list[Any]]:
		grouped: dict[str, list[Any]] = {}
		for attachment in self.attachments:
			grouped.setdefault(attachment.run, []).append(attachment)
		return grouped

	def _assert_not_blocked(self) -> None:
		blocking = frappe.db.get_value(
			"AI Run",
			{"session": self.name, "status": ("in", ["Paused", "Running"])},
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


def _row_to_message(row) -> dict[str, Any]:
	"""Convert a stored transcript row to an OpenAI-format message dict."""
	if row.role == "tool":
		return {"role": "tool", "tool_call_id": row.tool_call_id, "content": row.content or ""}
	message: dict[str, Any] = {"role": row.role, "content": row.content}
	if row.tool_calls:
		message["tool_calls"] = json.loads(row.tool_calls)
	return message


def _inject_file_text(content: str | None, attachments: list[Any]) -> str:
	"""Append attached-file text to a user message, clearly delimited as data for the model."""
	blocks = [
		f"--- File: {a.file_name} ---\n{a.extracted_text}\n--- End of file: {a.file_name} ---"
		for a in attachments
	]
	files = "\n\n".join(blocks)
	body = f"{_('The user attached the following file(s):')}\n\n{files}"
	return f"{content}\n\n{body}" if content else body


def derive_title(text: str) -> str:
	"""Pick a short title from a user message. Single line, capped at TITLE_MAX_LENGTH."""
	cleaned = " ".join((text or "").split())
	if len(cleaned) <= TITLE_MAX_LENGTH:
		return cleaned
	return cleaned[: TITLE_MAX_LENGTH - 1].rstrip() + "…"
