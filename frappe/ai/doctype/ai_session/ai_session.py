# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document

TITLE_MAX_LENGTH = 80


class AISession(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.ai.doctype.ai_session_message.ai_session_message import AISessionMessage
		from frappe.types import DF

		agent: DF.Link | None
		messages: DF.Table[AISessionMessage]
		title: DF.Data | None
	# end: auto-generated types

	def validate(self):
		self._validate_agent_unchanged()

	def _validate_agent_unchanged(self):
		"""The agent that drives a session is fixed at creation. Subsequent turns must use the same agent."""
		if self.is_new():
			return
		db_agent = frappe.db.get_value("AI Session", self.name, "agent")
		if db_agent != self.agent:
			frappe.throw(
				_("Cannot change the agent on an existing session."),
				title=_("Agent Locked"),
			)

	def transcript(self) -> list[dict[str, Any]]:
		"""Return the conversation history in OpenAI message format."""
		out: list[dict[str, Any]] = []
		for row in self.messages:
			message: dict[str, Any] = {"role": row.role}
			if row.role == "tool":
				message["tool_call_id"] = row.tool_call_id
				message["content"] = row.content or ""
			else:
				message["content"] = row.content
				if row.tool_calls:
					message["tool_calls"] = json.loads(row.tool_calls)
			out.append(message)
		return out

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


def derive_title(text: str) -> str:
	"""Pick a short title from a user message. Single line, capped at TITLE_MAX_LENGTH."""
	cleaned = " ".join((text or "").split())
	if len(cleaned) <= TITLE_MAX_LENGTH:
		return cleaned
	return cleaned[: TITLE_MAX_LENGTH - 1].rstrip() + "…"
