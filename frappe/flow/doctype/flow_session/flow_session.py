# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
from contextlib import suppress
from typing import TYPE_CHECKING, Any

import frappe
from frappe import _
from frappe.model.document import Document

from flow.daemon.client import DaemonClient, DaemonError
from flow.lib.session import ABANDONED, GONE, READ_ONLY, STOPPED, LogRecorder, fail_running, flow_server

if TYPE_CHECKING:
	from flow.flow.doctype.flow_run.flow_run import FlowRun

CALLBACK_METHOD = "flow.daemon.callback.callback"


class FlowSession(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from flow.flow.doctype.flow_session_attachment.flow_session_attachment import FlowSessionAttachment
		from flow.flow.doctype.flow_session_message.flow_session_message import FlowSessionMessage

		agent: DF.Link
		attachments: DF.Table[FlowSessionAttachment]
		auto_approve: DF.Check
		last_synced_seq: DF.Int
		messages: DF.Table[FlowSessionMessage]
		model: DF.Link | None
		source: DF.Literal["Manual", "Trigger"]
		title: DF.Data | None
	# end: auto-generated types

	def validate(self):
		self._validate_agent_unchanged()
		self._validate_model_enabled()
		if self.source == "Trigger":
			self.auto_approve = 1

	def on_trash(self):
		try:
			_delete_server_session(self.name)
		except DaemonError as exc:
			frappe.throw(str(exc), title=_("Flow Server"))
		frappe.db.delete("Flow Run", {"session": self.name})
		_purge_attachment_chunks(self.name)

	def _validate_model_enabled(self):
		if not self.model:
			return
		if not frappe.db.get_value("Flow Model", self.model, "enabled"):
			frappe.throw(
				_("Flow Model {0} is disabled.").format(self.model),
				title=_("Disabled Model"),
			)

	def _validate_agent_unchanged(self):
		"""The agent that drives a session is fixed at creation. Subsequent turns must use the same agent."""
		if self.is_new():
			return
		db_agent = frappe.db.get_value("Flow Session", self.name, "agent")
		if db_agent != self.agent:
			frappe.throw(
				_("Cannot change the agent on an existing session."),
				title=_("Agent Locked"),
			)

	@staticmethod
	def clear_old_logs(days=30):
		"""Delete sessions idle for `days` with their runs, transcript and server copies."""
		cutoff = frappe.utils.add_days(frappe.utils.now(), -days)
		sessions = frappe.get_all("Flow Session", filters={"modified": ["<", cutoff]}, pluck="name")
		for batch in frappe.utils.create_batch(sessions, 100):
			try:
				for name in batch:
					_delete_server_session(name)
			except DaemonError:
				frappe.log_error(title="Flow Session purge stopped: the flow server refused")
				return
			frappe.db.delete("Flow Run", {"session": ["in", batch]})
			frappe.db.delete("Flow Session Message", {"parent": ["in", batch]})
			_delete_attachment_files(batch)
			frappe.db.delete("Flow Session Attachment", {"parent": ["in", batch]})
			frappe.db.delete("Flow Session", {"name": ["in", batch]})
			_purge_attachment_chunks(batch)

	def transcript(self) -> list[dict[str, Any]]:
		"""Return the conversation history in OpenAI message format."""
		return [_row_to_message(row) for row in self.messages]

	def server_config(self) -> dict[str, Any]:
		"""This session's flow server config. Tools go as schemas; the server calls back to run them."""
		from flow.daemon import lifecycle
		from flow.flow.doctype.flow_agent.flow_agent import DEFAULT_MAX_ITERATIONS
		from flow.lib.model import model_config

		agent = frappe.get_doc("Flow Agent", self.agent)
		if not agent.enabled:
			frappe.throw(_("Flow Agent {0} is disabled.").format(agent.name), title=_("Disabled Agent"))
		config = {
			"session_id": self.name,
			"title": self.title,
			**model_config(self.model or agent.model),
			"system_prompt": agent.instructions or "",
			"tools": [],
			"extension_tools": [],
			"skills_enabled": False,
			**agent.client_tool_config(self.name),
			"auto_approve": bool(self.auto_approve),
			"max_turns": agent.max_iterations or DEFAULT_MAX_ITERATIONS,
			"auto_compact": True,
			"callback_url": f"{lifecycle.site_url()}/api/method/{CALLBACK_METHOD}",
			"callback_token": frappe.conf.flow_server_secret,
			"notify_run_ended": True,
			"user_context": {
				"site": frappe.local.site,
				"user": frappe.session.user,
				"agent": self.agent,
				"session": self.name,
			},
			"cwd": str(lifecycle.session_root()),
		}
		if frappe.conf.flow_callback_timeout:
			config["callback_timeout"] = frappe.conf.flow_callback_timeout
		return config

	def chat(
		self,
		input: str,
		*,
		attachments: list[str] | None = None,
		source: str = "Manual",
		trigger: str | None = None,
		reference_doctype: str | None = None,
		reference_name: str | None = None,
	) -> FlowRun:
		"""Start a turn and return its Running Flow Run, or the active run it joined.
		`attachments` are File names whose content travels with this turn."""
		from flow.flow.doctype.flow_session_attachment.flow_session_attachment import (
			build_turn,
			cleanup_indexed_files,
		)
		from flow.memory.memory import memory_block

		if not (input or "").strip():
			frappe.throw(_("Message is required."), title=_("Invalid Message"))
		self._assert_can_run()
		self.sync()
		turn = build_turn(self, input, attachments or [])
		turn.message += memory_block(self.agent, self.owner, input)
		uploaded = []
		try:
			with DaemonClient.for_site() as client:
				try:
					if turn.images:
						uploaded = [
							a["id"] for a in client.upload_attachments(self.name, turn.images)["attachments"]
						]
					reply = client.run(self.name, turn.message, attachments=uploaded)
				except DaemonError:
					if uploaded:
						with suppress(DaemonError):
							client.cleanup_attachments(self.name, uploaded)
					raise
		except DaemonError as exc:
			cleanup_indexed_files(self.name, turn.indexed_files)
			if exc.status == 404:
				frappe.throw(_(READ_ONLY), title=_("Flow Server"))
			frappe.throw(str(exc), title=_("Flow Server"))
		if reply.get("status") == "steered":
			run = self._active_run()
		else:
			run = frappe.get_doc(
				{
					"doctype": "Flow Run",
					"session": self.name,
					"source": source,
					"input": input,
					"trigger": trigger,
					"reference_doctype": reference_doctype,
					"reference_name": reference_name,
					"status": "Running",
				}
			).insert(ignore_permissions=True)
		if turn.attachment_rows:
			for row in turn.attachment_rows:
				self.append("attachments", {**row, "run": run.name})
			self.save(ignore_permissions=True)
		return run

	def resume(self, answers: dict[str, Any]) -> FlowRun:
		"""Answer the paused run's approval batch, keyed by tool call id."""
		self._assert_can_run()
		self.sync()
		run = self._paused_run()
		with flow_server() as client:
			client.resume(self.name, answers, approval_seq=run.approval_seq)
		run.db_set({"status": "Running", "questions": None, "approval_seq": 0})
		return run

	def abort(self) -> str:
		"""Signal the active turn to stop; its terminal callback records the outcome."""
		with flow_server() as client:
			return client.abort(self.name)["status"]

	def cancel_pending(self) -> str:
		"""Drop the paused run's approval batch: the run is over, stopped by the user."""
		with flow_server() as client:
			status = client.cancel_pending(self.name)["status"]
		if status == "cancelled":
			self.sync()
		return status

	def _assert_can_run(self) -> None:
		"""Enforce current agent and model access before the daemon uses its stored config."""
		from flow.lib.model import model_config

		agent = frappe.get_doc("Flow Agent", self.agent)
		frappe.has_permission("Flow Agent", "read", agent.name, throw=True)
		if not agent.enabled:
			frappe.throw(_("Flow Agent {0} is disabled.").format(agent.name), title=_("Disabled Agent"))
		model_config(self.model or agent.model)

	def set_model(self, model: str) -> None:
		from flow.lib.model import model_config

		config = model_config(model)
		with flow_server() as client:
			client.set_model(
				self.name, config["model"], api_key=config["api_key"], api_base=config["api_base"]
			)
		self.db_set("model", model)

	def set_title(self, title: str) -> None:
		with flow_server() as client:
			client.patch_config(self.name, title=title)
		self.db_set("title", title)

	def set_auto_approve(self, auto_approve: bool) -> None:
		"""Whether confirmation tools run unattended; applies from the next tool call."""
		auto_approve = bool(auto_approve)
		if self.source == "Trigger" and not auto_approve:
			frappe.throw(_("Trigger sessions always auto-approve tool calls."))
		with flow_server() as client:
			client.patch_config(self.name, auto_approve=auto_approve)
		self.db_set("auto_approve", auto_approve)

	def entries(self, *, since: int = 0, path: str = "active") -> dict[str, Any]:
		"""The flow server's log: a snapshot of the active branch, or every row after `since`."""
		with flow_server() as client:
			return client.entries(self.name, since=since, path=path)

	def sync(self) -> None:
		"""Record the flow server's log since the last sync into Flow Runs and transcript rows."""
		self._lock()
		try:
			with DaemonClient.for_site() as client:
				info = client.get_session(self.name)
				rows = []
				if info["latest_seq"] > self.last_synced_seq:
					rows = client.entries(self.name, since=self.last_synced_seq, path="all")["entries"]
		except DaemonError as exc:
			if exc.status != 404:
				frappe.throw(str(exc), title=_("Flow Server"))
			fail_running(self.name, GONE)
			return
		if rows:
			LogRecorder(self).record(rows)
		if not info["running"]:
			fail_running(self.name, ABANDONED)
		if info["state"] == "idle":
			for name in frappe.get_all(
				"Flow Run", filters={"session": self.name, "status": "Paused"}, pluck="name"
			):
				frappe.db.set_value("Flow Run", name, {"status": "Failed", "error": STOPPED})
		if info["title"] and info["title"] != self.title:
			self.title = info["title"]
		self.flags.ignore_validate = True
		self.save(ignore_permissions=True)

	def _lock(self) -> None:
		"""Lock this session's row for the transaction and re-read it."""
		frappe.db.get_value("Flow Session", self.name, "name", for_update=True)
		self.reload()

	def _active_run(self) -> FlowRun:
		name = frappe.db.get_value(
			"Flow Run", {"session": self.name, "status": "Running"}, "name", order_by="creation desc"
		)
		if not name:
			frappe.throw(
				_("The flow server is running a turn this site has no record of."), title=_("Flow Server")
			)
		return frappe.get_doc("Flow Run", name)

	def _paused_run(self) -> FlowRun:
		name = frappe.db.get_value(
			"Flow Run", {"session": self.name, "status": "Paused"}, "name", order_by="creation desc"
		)
		if not name:
			frappe.throw(_("This session has no paused run."), title=_("Nothing to Resume"))
		return frappe.get_doc("Flow Run", name)


def _delete_server_session(name: str) -> None:
	"""Drop the flow server's copy of a session; one it no longer has is fine."""
	with DaemonClient.for_site() as client:
		try:
			client.delete_session(name)
		except DaemonError as exc:
			if exc.status != 404:
				raise


def _delete_attachment_files(sessions: list[str]) -> None:
	"""Delete the uploaded File docs attached to these sessions. Per-doc (not bulk SQL)
	so File.on_trash runs to remove the on-disk content, and best-effort so one failure
	never aborts the purge."""
	files = frappe.get_all("Flow Session Attachment", filters={"parent": ["in", sessions]}, pluck="file")
	for file in set(filter(None, files)):
		if frappe.db.get_value("File", file, "attached_to_doctype"):
			continue
		if frappe.db.exists("Flow Session Attachment", {"file": file, "parent": ["not in", sessions]}):
			continue
		try:
			frappe.delete_doc("File", file, ignore_permissions=True, force=True, delete_permanently=True)
		except Exception:
			frappe.log_error(title="Chat attachment file cleanup failed")


def _purge_attachment_chunks(session: str | list[str]) -> None:
	"""Best-effort removal of a session's (or batch's) retrieval chunks. The chunk index is
	disposable, so a failure here must never block deleting the session."""
	from flow.knowledge import attachment_store

	try:
		attachment_store.delete(session=session)
	except Exception:
		frappe.log_error(title="Chat attachment cleanup failed")


def _row_to_message(row) -> dict[str, Any]:
	"""Convert a stored transcript row to an OpenAI-format message dict."""
	if row.role == "tool":
		return {"role": "tool", "tool_call_id": row.tool_call_id, "content": row.content or ""}
	message: dict[str, Any] = {"role": row.role, "content": row.content}
	if row.tool_calls:
		message["tool_calls"] = json.loads(row.tool_calls)
	return message
