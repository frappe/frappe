# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from __future__ import annotations

import json
from contextlib import suppress
from typing import TYPE_CHECKING, Any

import redis

import frappe
from frappe import _
from frappe.flow.daemon.client import DaemonClient, DaemonError
from frappe.flow.daemon.lifecycle import _redis_url
from frappe.flow.lib.session import (
	ABANDONED,
	GONE,
	READ_ONLY,
	STOPPED,
	LogRecorder,
	call_on_complete,
	fail_running,
	flow_server,
	sync_with_retry,
)
from frappe.model.document import Document

if TYPE_CHECKING:
	from frappe.flow.doctype.flow_run.flow_run import FlowRun

COMPACT_INPUT = "/compact"  # a compaction's run has no message of its own


class FlowSession(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.flow.doctype.flow_session_attachment.flow_session_attachment import FlowSessionAttachment
		from frappe.flow.doctype.flow_session_message.flow_session_message import FlowSessionMessage
		from frappe.types import DF

		agent: DF.Link
		attachments: DF.Table[FlowSessionAttachment]
		auto_approve: DF.Check
		last_synced_seq: DF.Int
		messages: DF.Table[FlowSessionMessage]
		model: DF.Link | None
		source: DF.Literal["Manual", "Trigger"]
		title: DF.Data | None
	# end: auto-generated types

	def before_insert(self):
		# the flow server keeps the model a chat starts on, so the chat names it, not the agent
		self.model = self.model or frappe.db.get_value("Flow Agent", self.agent, "model")

	def validate(self):
		self._validate_agent_unchanged()
		self._validate_model_enabled()
		if self.source == "Trigger":
			self.auto_approve = 1

	def on_update(self):
		# a model saved on the record, as from Desk, must reach the flow server too
		if not self.flags.in_insert and self.has_value_changed("model"):
			self._send_model(self.model or frappe.db.get_value("Flow Agent", self.agent, "model"))

	def on_trash(self):
		try:
			_delete_server_session(self.name)
		except DaemonError as exc:
			frappe.throw(str(exc), title=_("Flow Server"))
		frappe.db.delete("Flow Run", {"session": self.name})
		_purge_attachment_chunks(self.name)

	def validate_share(self, docshare):
		"""Shared to view only: whoever writes to a session acts as its owner, and only they share it."""
		if docshare.write or docshare.share:
			frappe.throw(_("A chat can only be shared to view."), title=_("View Only"))
		# Frappe's everyone reaches portal users too; General access keeps it to Flow users
		if docshare.everyone and docshare.read:
			frappe.throw(
				_("To share a chat with everyone, use General access in its Share dialog."),
				title=_("Not Allowed"),
			)

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
			frappe.db.delete("DocShare", {"share_doctype": "Flow Session", "share_name": ["in", batch]})
			# what sharing leaves on a session: its Shared / Unshared comments and notifications
			frappe.db.delete(
				"Comment", {"reference_doctype": "Flow Session", "reference_name": ["in", batch]}
			)
			frappe.db.delete(
				"Notification Log", {"document_type": "Flow Session", "document_name": ["in", batch]}
			)
			frappe.db.delete("Flow Session", {"name": ["in", batch]})
			_purge_attachment_chunks(batch)

	def transcript(self) -> list[dict[str, Any]]:
		"""Return the conversation history in OpenAI message format."""
		return [_row_to_message(row) for row in self.messages]

	def server_config(self) -> dict[str, Any]:
		"""This session's flow server config. Tools go as schemas; the server calls back to run them."""
		from frappe.flow.daemon import lifecycle
		from frappe.flow.doctype.flow_agent.flow_agent import DEFAULT_MAX_ITERATIONS
		from frappe.flow.lib.model import model_config

		agent = frappe.get_doc("Flow Agent", self.agent)
		if not agent.enabled:
			frappe.throw(_("Flow Agent {0} is disabled.").format(agent.name), title=_("Disabled Agent"))
		# no agent name: the callback reads it from this session, which a rename keeps current
		context = {
			"site": frappe.local.site,
			"user": frappe.session.user,
			"session": self.name,
		}
		config = {
			"session_id": self.name,
			"title": self.title,
			**model_config(self.model or agent.model),
			**agent.session_tool_config(self.name),
			"subagents": agent.subagent_configs(self.name, context),
			"skills_enabled": False,
			"auto_approve": bool(self.auto_approve),
			"max_turns": agent.max_iterations or DEFAULT_MAX_ITERATIONS,
			"auto_compact": True,
			"callback_url": lifecycle.callback_url(),
			"callback_token": frappe.conf.flow_server_secret,
			"notify_run_ended": True,
			"user_context": context,
			"cwd": str(lifecycle.session_root()),
		}
		if agent.token_budget:  # none: no cap
			config["token_budget"] = agent.token_budget
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
		on_complete: str | None = None,
	) -> FlowRun:
		"""Start a turn and return its Running Flow Run, or the active run it joined.
		`attachments` are File names whose content travels with this turn; with them, `input`
		may be empty. Once the run ends, Flow calls the function at the dotted path
		`on_complete` with it."""
		from frappe.flow.doctype.flow_session_attachment.flow_session_attachment import (
			build_turn,
			cleanup_indexed_files,
		)
		from frappe.flow.doctype.flow_skill.flow_skill import expand_skill_command
		from frappe.flow.memory.memory import memory_block

		if not (input or "").strip() and not attachments:
			frappe.throw(_("Message is required."), title=_("Invalid Message"))
		self._assert_can_run()
		self.sync()
		turn = build_turn(self, expand_skill_command(self.agent, input), attachments or [])
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
			if on_complete and not run.on_complete:  # a run keeps the first on_complete it is given
				run.db_set("on_complete", on_complete)
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
					"on_complete": on_complete,
				}
			).insert(ignore_permissions=True)
		if turn.attachment_rows:
			for row in turn.attachment_rows:
				_claim_attachment_file(self.name, row["file"])
				self.append("attachments", {**row, "run": run.name})
			self.save(ignore_permissions=True)
		return run

	def resume(self, answers: dict[str, Any], approval_seq: int | None = None) -> FlowRun:
		"""Answer the paused run's approval batch, keyed by tool call id; `approval_seq` names
		a sub-agent's batch instead, which the run kept running through."""
		self._assert_can_run()
		sync_with_retry(self)
		run = self._paused_run(approval_seq)
		with flow_server() as client:
			client.resume(self.name, answers, approval_seq=approval_seq or run.approval_seq)
		if run.status == "Paused":
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
			sync_with_retry(self)
			call_on_complete(self)
		return status

	def rewind(self, target_seq: int) -> str:
		"""Branch the conversation from entry `target_seq`; refused while a run waits for approval."""
		with flow_server() as client:
			status = client.rewind(self.name, target_seq)["status"]
		sync_with_retry(self)
		return status

	def compact(self) -> FlowRun:
		"""Summarize the conversation so far into a shorter context; the summary call is a run."""
		self._assert_can_run()
		# the sync locks this session, so the run-end callback can't record the run before its row exists
		sync_with_retry(self)
		with flow_server() as client:
			client.compact(self.name)
		return frappe.get_doc(
			{
				"doctype": "Flow Run",
				"session": self.name,
				"source": "Manual",
				"input": COMPACT_INPUT,
				"status": "Running",
			}
		).insert(ignore_permissions=True)

	def _assert_can_run(self) -> None:
		"""Enforce current agent and model access before the daemon uses its stored config."""
		from frappe.flow.lib.model import model_config

		agent = frappe.get_doc("Flow Agent", self.agent)
		frappe.has_permission("Flow Agent", "read", agent.name, throw=True)
		if not agent.enabled:
			frappe.throw(_("Flow Agent {0} is disabled.").format(agent.name), title=_("Disabled Agent"))
		model_config(self.model or agent.model)

	def set_model(self, model: str, reasoning_effort: str | None = None) -> None:
		self._send_model(model, reasoning_effort)
		self.db_set("model", model)

	def _send_model(self, model: str, reasoning_effort: str | None = None) -> None:
		from frappe.flow.lib.model import model_config

		config = model_config(model)
		with flow_server() as client:
			client.set_model(
				self.name,
				config["model"],
				api_key=config["api_key"],
				api_base=config["api_base"],
				model_params=config.get("model_params"),
				reasoning_effort=reasoning_effort,
			)

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
		files = {row.file for row in self.attachments if row.file}
		if files:
			existing = set(frappe.get_all("File", filters={"name": ("in", files)}, pluck="name"))
			if existing != files:
				self.set("attachments", [row for row in self.attachments if row.file in existing])

	def _active_run(self) -> FlowRun:
		name = frappe.db.get_value(
			"Flow Run", {"session": self.name, "status": "Running"}, "name", order_by="creation desc"
		)
		if not name:
			frappe.throw(
				_("The flow server is running a turn this site has no record of."), title=_("Flow Server")
			)
		return frappe.get_doc("Flow Run", name)

	def _paused_run(self, approval_seq: int | None = None) -> FlowRun:
		"""The Paused run, or the Running one when `approval_seq` names a sub-agent's batch."""
		name = frappe.db.get_value(
			"Flow Run", {"session": self.name, "status": "Paused"}, "name", order_by="creation desc"
		)
		if not name and approval_seq:
			name = frappe.db.get_value(
				"Flow Run", {"session": self.name, "status": "Running"}, "name", order_by="creation desc"
			)
		if not name:
			frappe.throw(_("This session has no paused run."), title=_("Nothing to Resume"))
		return frappe.get_doc("Flow Run", name)


def on_share_removed(share, method=None):
	"""A view of a chat taken back: the realtime relay re-checks who follows it live."""
	if share.share_doctype == "Flow Session":
		recheck_live_access(share.share_name, share.user)  # no user for an everyone share


def recheck_live_access(session: str, user: str | None = None) -> None:
	"""Once saved, have the relay ask `user` again, or with no user everyone but the owner."""
	notice = {
		"session": session,
		"user": user,
		"owner": frappe.db.get_value("Flow Session", session, "owner"),
	}
	frappe.db.after_commit.add(lambda: _publish_access_notice(notice))


def _publish_access_notice(notice: dict[str, Any]) -> None:
	if not (url := _redis_url()):
		return
	# with Redis down the relay isn't relaying either
	with suppress(redis.RedisError):
		redis.Redis.from_url(url).publish(f"flow-access:{frappe.local.site}", json.dumps(notice))


def _delete_server_session(name: str) -> None:
	"""Drop the flow server's copy of a session; one it no longer has is fine."""
	with DaemonClient.for_site() as client:
		try:
			client.delete_session(name)
		except DaemonError as exc:
			if exc.status != 404:
				raise


def _claim_attachment_file(session: str, file: str) -> None:
	"""Keep an accepted upload with its session so Frappe treats it as durable."""
	if frappe.db.get_value("File", file, "attached_to_doctype"):
		return
	frappe.db.set_value(
		"File",
		file,
		{
			"attached_to_doctype": "Flow Session",
			"attached_to_name": session,
			"attached_to_field": "attachments",
		},
		update_modified=False,
	)


def _delete_attachment_files(sessions: list[str]) -> None:
	"""Delete the uploaded File docs attached to these sessions. Per-doc (not bulk SQL)
	so File.on_trash runs to remove the on-disk content, and best-effort so one failure
	never aborts the purge."""
	files = frappe.get_all("Flow Session Attachment", filters={"parent": ["in", sessions]}, pluck="file")
	for file in {name for name in files if name}:
		attached = frappe.db.get_value(
			"File", file, ["attached_to_doctype", "attached_to_name"], as_dict=True
		)
		if attached and attached.attached_to_doctype not in (None, "", "Flow Session"):
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
	from frappe.flow.knowledge import attachment_store

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
