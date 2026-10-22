# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""A Flow Session on the flow server: starting one, loading one, and recording its log."""

from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import frappe
from frappe import _
from frappe.flow.daemon.client import DaemonClient, DaemonError

if TYPE_CHECKING:
	from frappe.flow.doctype.flow_agent.flow_agent import FlowAgent
	from frappe.flow.doctype.flow_run.flow_run import FlowRun
	from frappe.flow.doctype.flow_session.flow_session import FlowSession

STOPPED = "Stopped by user."
STATUS = {
	"done": "Completed",
	"length": "Completed",
	"denied": "Denied",
	"paused": "Paused",
	"max_turns": "Failed",
	"budget": "Failed",
	"aborted": "Failed",
	"error": "Failed",
}
ENDED = ("Completed", "Denied", "Failed")
ON_COMPLETE_SAVEPOINT = "flow_on_complete"
ERRORS = {
	"max_turns": "The agent hit its iteration limit.",
	"budget": "The agent hit its output token budget.",
	"aborted": STOPPED,
}
FAILED = "The run failed."
ABANDONED = "Run abandoned: the flow server stopped before it ended."
GONE = "Run abandoned: the flow server no longer has this session."
READ_ONLY = "This session's flow server copy is missing, so it is available as read-only history."
USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "cost")
PENDING_KEYS = ("id", "name", "args", "prompt")


def new_session(
	agent: FlowAgent | str | None = None,
	*,
	model: str | None = None,
	title: str | None = None,
	source: str = "Manual",
	auto_approve: bool = False,
) -> FlowSession:
	"""Start a Flow Session and its flow server twin. `agent` defaults to the Assistant."""
	if agent is None:
		agent_doc = frappe.get_doc("Flow Agent", _default_agent_name())
	else:
		agent_doc = frappe.get_doc("Flow Agent", agent) if isinstance(agent, str) else agent
	frappe.has_permission("Flow Agent", "read", agent_doc.name, throw=True)
	doc = frappe.get_doc(
		{
			"doctype": "Flow Session",
			"agent": agent_doc.name,
			"model": model,
			"title": title,
			"source": source,
			"auto_approve": source == "Trigger" or bool(auto_approve),
		}
	).insert(ignore_permissions=True)
	with flow_server() as client:
		client.create_session(doc.server_config())
	# The daemon's callbacks are separate requests: save the row now so they can find it.
	if not frappe.flags.in_test:
		frappe.db.commit()  # nosemgrep: frappe-manual-commit
	return doc


def load_session(name: str, *, agent: str | None = None, model: str | None = None) -> FlowSession:
	"""Continue a session by id; `model` switches its model first."""
	doc = frappe.get_doc("Flow Session", name)
	frappe.has_permission("Flow Session", "write", doc, throw=True)
	if agent and agent != doc.agent:
		frappe.throw(
			_("This session is bound to agent {0} and cannot be switched.").format(doc.agent),
			title=_("Agent Mismatch"),
		)
	if model and model != doc.model:
		doc.set_model(model)
	return doc


def warn_existing_sessions(agents: list[str]) -> None:
	"""A session's tools are fixed when the flow server creates it, so say so when a change
	cannot reach the sessions those agents already have."""
	if agents and frappe.db.exists("Flow Session", {"agent": ("in", agents)}):
		frappe.msgprint(
			_("Existing sessions keep the tools they started with. This applies to new sessions."),
			indicator="orange",
			alert=True,
		)


@contextmanager
def flow_server() -> Generator[DaemonClient]:
	"""This site's flow server client, whose refusals surface as validation errors."""
	try:
		with DaemonClient.for_site() as client:
			yield client
	except DaemonError as exc:
		frappe.throw(str(exc), title=_("Flow Server"))


class LogRecorder:
	"""Records one batch of the flow server's log rows into Flow Runs and transcript rows."""

	def __init__(self, session: FlowSession):
		self.session = session
		self.run = _latest_run(session.name)
		self.runs: dict[str, FlowRun] = {self.run.name: self.run} if self.run else {}
		self.matched_runs: set[str] = set()
		self.error: str | None = None

	def record(self, rows: list[dict]) -> None:
		for row in rows:
			kind = row["type"]
			if row.get("subagent_id") and kind != "usage":
				continue  # a sub-agent's rows are its own thread; only what it spent counts here
			if kind == "run_started":
				self.start_run(row["run_id"])
			elif kind == "user_message":
				self.add_user_message(_extract_text(row["content"]), row["seq"])
			elif kind == "assistant_message":
				self.add_assistant_message(*_assistant_text_and_tool_calls(row["content"]), row["seq"])
			elif kind == "tool_result":
				self.add_message("tool", row["content"], seq=row["seq"], tool_call_id=row["tool_call_id"])
			elif kind == "rewind":
				self.rewind(row["target_seq"])
			elif kind == "usage" and self.run:
				self.run.usage = _dump(_add_usage(_load(self.run.usage) or {}, row))
			elif kind == "approval_required" and self.run:
				self.run.questions = _dump(
					[{key: call.get(key) for key in PENDING_KEYS} for call in row["calls"]]
				)
				self.run.approval_seq = row["seq"]
			elif kind == "run_error":
				self.error = row["message"]
			elif kind == "run_ended" and self.run:
				self.end_run(row["reason"])
		for run in self.runs.values():
			run.save(ignore_permissions=True)
		self.session.last_synced_seq = rows[-1]["seq"]

	def start_run(self, run_id: str) -> None:
		"""A resume continues the paused run; anything else takes the oldest open run, else a new row."""
		run = self.run if self.run and self.run.status == "Paused" else self._find_or_create_run()
		run.daemon_run_id = run_id
		run.status = "Running"
		run.questions = None
		run.approval_seq = 0
		self.run = run
		self.runs[run.name] = run
		self.matched_runs.add(run.name)
		self.error = None

	def _find_or_create_run(self) -> FlowRun:
		filters: dict[str, Any] = {"session": self.session.name, "status": ("in", ("Running", "Paused"))}
		if self.matched_runs:
			filters["name"] = ("not in", list(self.matched_runs))
		name = frappe.db.get_value("Flow Run", filters, "name", order_by="creation asc")
		if name in self.runs:
			return self.runs[name]
		if name:
			return frappe.get_doc("Flow Run", name)
		return frappe.get_doc(
			{
				"doctype": "Flow Run",
				"session": self.session.name,
				"source": self.session.source,
				"status": "Running",
			}
		).insert(ignore_permissions=True)

	def add_user_message(self, text: str, seq: int) -> None:
		if self.run and not self.run.input:
			self.run.input = text
		self.add_message("user", text, seq=seq)

	def add_assistant_message(self, text: str, calls: list[dict], seq: int) -> None:
		if self.run:
			self.run.iterations = (self.run.iterations or 0) + 1
			self.run.output = text or self.run.output
			self.run.tool_calls = _dump((_load(self.run.tool_calls) or []) + calls)
		self.add_message(
			"assistant",
			text or None,
			seq=seq,
			tool_calls=_dump(_to_openai_tool_calls(calls)) if calls else None,
		)

	def rewind(self, target_seq: int) -> None:
		"""Drop the transcript rows logged after the entry the conversation went back to."""
		self.session.set("messages", [row for row in self.session.messages if row.seq <= target_seq])

	def end_run(self, reason: str) -> None:
		run = self.run
		run.status = STATUS.get(reason, "Failed")
		run.error = (self.error or ERRORS.get(reason, FAILED)) if run.status == "Failed" else None
		if run.status != "Paused":
			run.questions = None
			run.approval_seq = 0

	def add_message(self, role: str, content: str | None, **fields: Any) -> None:
		run = self.run.name if self.run else None
		self.session.append("messages", {"role": role, "content": content, "run": run, **fields})


def fail_running(session_name: str, error: str) -> None:
	for name in frappe.get_all(
		"Flow Run", filters={"session": session_name, "status": "Running"}, pluck="name"
	):
		frappe.db.set_value("Flow Run", name, {"status": "Failed", "error": error})


def sync_with_retry(session: FlowSession) -> None:
	"""Sync, again in a new transaction if a concurrent sync commits first; call before any write."""
	try:
		session.sync()
	except (frappe.TimestampMismatchError, frappe.QueryDeadlockError):
		frappe.db.rollback()  # our reads predate its commit
		session.sync()


def call_on_complete(session: FlowSession) -> None:
	"""Call each ended run's on_complete once, only in the session owner's request so it runs as
	them; another user's request leaves it for theirs. A failing one is logged and undone."""
	if frappe.session.user != session.owner:
		return
	for name in frappe.get_all(
		"Flow Run",
		filters={"session": session.name, "status": ("in", ENDED), "on_complete": ("is", "set")},
		pluck="name",
	):
		# locked by name: a locking scan would lock every run on the site
		on_complete = frappe.db.get_value("Flow Run", name, "on_complete", for_update=True)
		if not on_complete:  # another request called it first
			continue
		frappe.db.set_value("Flow Run", name, "on_complete", None, update_modified=False)
		frappe.db.savepoint(ON_COMPLETE_SAVEPOINT)
		try:
			frappe.get_attr(on_complete)(frappe.get_doc("Flow Run", name))
		except Exception:
			frappe.db.rollback(save_point=ON_COMPLETE_SAVEPOINT)
			frappe.log_error(
				title="Flow Run on_complete failed", reference_doctype="Flow Run", reference_name=name
			)


def _latest_run(session_name: str) -> FlowRun | None:
	name = frappe.db.get_value("Flow Run", {"session": session_name}, "name", order_by="creation desc")
	return frappe.get_doc("Flow Run", name) if name else None


def _extract_text(content: str | list[dict]) -> str:
	if isinstance(content, str):
		return content
	return "".join(block["text"] for block in content if block["type"] == "text")


def _assistant_text_and_tool_calls(content: list[dict]) -> tuple[str, list[dict]]:
	calls = [
		{"id": block["id"], "name": block["name"], "arguments": block["arguments"]}
		for block in content
		if block["type"] == "tool_call"
	]
	return _extract_text(content), calls


def _to_openai_tool_calls(calls: list[dict]) -> list[dict]:
	"""The transcript keeps the OpenAI tool-call shape the desk transcript renders."""
	return [
		{
			"id": call["id"],
			"type": "function",
			"function": {"name": call["name"], "arguments": json.dumps(call["arguments"])},
		}
		for call in calls
	]


def _add_usage(total: dict[str, Any], row: dict) -> dict[str, Any]:
	for key in USAGE_KEYS:
		total[key] = total.get(key, 0) + row.get(key, 0)
	return total


def _load(value: str | None) -> Any:
	return json.loads(value) if value else None


def _dump(value: Any) -> str:
	return json.dumps(value, default=str)


def _default_agent_name() -> str:
	from frappe.flow.assistant import ASSISTANT_AGENT_TITLE

	if not frappe.db.exists("Flow Agent", ASSISTANT_AGENT_TITLE):
		frappe.throw(
			_("The {0} agent is missing. Create a Flow Model first to auto-provision it.").format(
				ASSISTANT_AGENT_TITLE
			),
			title=_("Missing Default Agent"),
		)
	return ASSISTANT_AGENT_TITLE
