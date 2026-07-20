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

	from flow.flow.doctype.flow_run.flow_run import FlowRun
	from flow.lib.agent import Event

TITLE_MAX_LENGTH = 80
# A "Running" run older than this is treated as abandoned and no longer blocks the session.
RUNNING_STALE_SECONDS = 300

# Attachment routing. A file whose text exceeds RETRIEVAL_FRACTION of the model's
# context window is too big to inline every turn, so it is chunked and retrieved
# instead. Tokens are estimated from characters (no per-turn tokenizer cost).
DEFAULT_CONTEXT_WINDOW = 128000
CHARS_PER_TOKEN = 4
RETRIEVAL_FRACTION = 0.5
# Chars reserved (as tokens) for the model's reply when budgeting file content.
RESERVED_OUTPUT_TOKENS = 4096
# How many retrieved chunks to inject for the current turn.
RETRIEVAL_TOP_K = 8


def _set_active_run(run: str | None) -> None:
	"""Record which run is executing, so memories the update_memory tool creates during it
	are stamped with this run as their source_run. flow.memory.memory reads this flag;
	stream_with_persistence clears it when a streamed run ends."""
	frappe.flags.flow_run = run


class FlowSession(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from flow.flow.doctype.flow_session_attachment.flow_session_attachment import FlowSessionAttachment
		from flow.flow.doctype.flow_session_message.flow_session_message import FlowSessionMessage

		agent: DF.Link | None
		attachments: DF.Table[FlowSessionAttachment]
		messages: DF.Table[FlowSessionMessage]
		model: DF.Link | None
		source: DF.Literal["Manual", "Trigger"]
		title: DF.Data | None
	# end: auto-generated types

	def validate(self):
		self._validate_agent_unchanged()
		self._validate_model_enabled()

	def on_trash(self):
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
		if (db_agent or None) != (self.agent or None):
			frappe.throw(
				_("Cannot change the agent on an existing session."),
				title=_("Agent Locked"),
			)

	@staticmethod
	def clear_old_logs(days=30):
		"""Delete sessions idle for `days`, along with their Flow Runs and transcript rows.
		Age is last activity (modified), so an actively-used session is never purged."""
		cutoff = frappe.utils.add_days(frappe.utils.now(), -days)
		sessions = frappe.get_all("Flow Session", filters={"modified": ["<", cutoff]}, pluck="name")
		for batch in frappe.utils.create_batch(sessions, 100):
			frappe.db.delete("Flow Run", {"session": ["in", batch]})
			frappe.db.delete("Flow Session Message", {"parent": ["in", batch]})
			_delete_attachment_files(batch)
			frappe.db.delete("Flow Session Attachment", {"parent": ["in", batch]})
			frappe.db.delete("Flow Session", {"name": ["in", batch]})
			_purge_attachment_chunks(batch)

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
		auto_approve: bool = False,
		stream: bool = False,
	) -> FlowRun | Generator[Event]:
		"""Run one turn and persist it as a Flow Run. `attachments` are File names whose text
		is injected into this turn's prompt. With `stream=True`, returns an event generator.

		Commits the current transaction before the model call (to release row locks). Do not
		call with pending writes you may want to roll back on failure; commit-and-compensate
		around it instead."""
		from flow.flow.doctype.flow_run.flow_run import create_run, stream_with_persistence

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
		self._index_retrieval_attachments(run.name, {d["file"]: d["extracted_text"] for d in attachment_data})
		run_input = self._build_prompt_messages()

		# Release row locks and publish the Running run before the long model call, so a
		# concurrent turn doesn't block on the Flow Session row until lock timeout (1205).
		if not frappe.flags.in_test:
			frappe.db.commit()

		# Opt-in (set on the Flow Trigger): run confirmation tools without approval so unattended
		# trigger runs don't park in Paused waiting for a confirmation no one can give.
		self._runtime.auto_approve = auto_approve

		# The update_memory tool reads this to stamp source_run. Scope tightly to the runtime
		# call and clear after, so a stale run never leaks onto a later write in this request.
		_set_active_run(run.name)
		if stream:
			return stream_with_persistence(lambda: self._runtime.run(run_input, stream=True), run)

		try:
			result = self._runtime.run(run_input)
		except Exception as e:
			run.mark_failed(str(e))
			# Persist Failed too; the Running run is already committed.
			if not frappe.flags.in_test:
				frappe.db.commit()
			raise
		finally:
			_set_active_run(None)
		run.apply_result(result)
		return run

	def _load_attachments(self, attachments: list[str] | None) -> list[dict[str, Any]]:
		"""Validate and extract each attached file (errors surface before the run is created)."""
		from flow.flow.doctype.flow_session_attachment.flow_session_attachment import resolve_attachment

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

		threshold = self._attachment_inline_threshold()
		embeddings_on = _embeddings_configured()
		for data in attachment_data:
			text = data["extracted_text"]
			self.append(
				"attachments",
				{
					"file": data["file"],
					"file_name": data["file_name"],
					"file_size": data["file_size"],
					"extracted_text": text[:threshold],
					"mode": _route_attachment(text, threshold, embeddings_on),
					"run": run,
				},
			)
		self.save(ignore_permissions=True)

	def _context_window(self) -> int:
		"""The effective model's context window in tokens (a default when unknown)."""
		model = (self._snapshot or {}).get("model")
		return (
			model and frappe.db.get_value("Flow Model", model, "context_window")
		) or DEFAULT_CONTEXT_WINDOW

	def _attachment_inline_threshold(self) -> int:
		"""Max characters of file text to inline before switching a file to retrieval."""
		return int(self._context_window() * CHARS_PER_TOKEN * RETRIEVAL_FRACTION)

	def _file_injection_budget(self) -> int:
		"""Characters left for file content this turn: the context window minus the reply
		reservation and the conversation text already in the transcript. Shrinks as the
		conversation grows, so inline files yield to the dialogue rather than overflow it."""
		window_chars = self._context_window() * CHARS_PER_TOKEN
		reserved = RESERVED_OUTPUT_TOKENS * CHARS_PER_TOKEN
		dialogue = sum(len(m.content or "") for m in self.messages)
		return max(0, window_chars - reserved - dialogue)

	def _index_retrieval_attachments(self, run: str, texts: dict[str, str] | None = None) -> None:
		"""Chunk, embed, and store this run's retrieval-mode attachments, preferring the full
		in-memory `texts` over the (capped) row text. Demotes to Inline on failure."""
		rows = [a for a in self.attachments if a.run == run and a.mode == "Retrieval"]
		if not rows:
			return

		from frappe.utils import cint

		from flow.knowledge import attachment_store
		from flow.knowledge.chunker import chunk_text
		from flow.knowledge.embedder import embed_texts

		texts = texts or {}
		settings = frappe.get_cached_doc("Flow Knowledge Settings")
		for row in rows:
			try:
				chunks = chunk_text(
					texts.get(row.file) or row.extracted_text,
					chunk_size=cint(settings.chunk_size),
					overlap=cint(settings.chunk_overlap),
				)
				if not chunks:
					row.db_set("mode", "Inline")
					continue
				vectors = embed_texts(chunks)
				attachment_store.ensure_table(cint(settings.embedding_dimension))
				attachment_store.add(self.name, row.name, chunks, vectors)
			except Exception:
				frappe.log_error(title="Chat attachment indexing failed")
				row.db_set("mode", "Inline")

	def resume(self, answers: dict[str, Any], *, stream: bool = False) -> FlowRun | Generator[Event]:
		"""Resume this session's paused run with the user's answers."""
		from flow.flow.doctype.flow_run.flow_run import stream_with_persistence

		run_name = frappe.db.get_value(
			"Flow Run",
			{"session": self.name, "status": "Paused"},
			"name",
			order_by="creation desc",
		)
		if not run_name:
			frappe.throw(_("This session has no paused run to resume."), title=_("Nothing to Resume"))
		run = frappe.get_doc("Flow Run", run_name)

		self.reload()
		messages = self._build_prompt_messages()
		if not messages:
			frappe.throw(_("This session has no transcript to resume from."))

		_set_active_run(run.name)
		if stream:
			return stream_with_persistence(lambda: self._runtime.resume(messages, answers, stream=True), run)

		try:
			result = self._runtime.resume(messages, answers)
		except Exception as e:
			run.mark_failed(str(e))
			raise
		finally:
			_set_active_run(None)
		run.apply_result(result)
		return run

	def _build_prompt_messages(self) -> list[dict[str, Any]]:
		"""Transcript as sent to the model. Augmentation is ephemeral — stored messages stay
		clean (file text lives only in the attachments child table):

		- Inline files: full text re-injected on their turn, clamped to the remaining budget.
		- Retrieval files: a short note marks where each was attached; for the latest user turn
		  the most relevant chunks (by that turn's query) are injected in place of the full text.
		- Agent memory: the agent's saved memories are appended to the system message.
		"""
		from flow.knowledge.retriever import retrieve_attachments
		from flow.memory.memory import build_memory_block

		attachments_by_run = self._group_attachments_by_run()
		last_user_run = self._latest_user_run()
		query = self._latest_user_content() if any(a.mode == "Retrieval" for a in self.attachments) else None
		budget = self._file_injection_budget()

		messages: list[dict[str, Any]] = []
		for row in self.messages:
			message = _row_to_message(row)
			if row.role == "user":
				content = message["content"]
				attachments = attachments_by_run.get(row.run, [])
				inline = [a for a in attachments if a.mode == "Inline"]
				retrieval = [a for a in attachments if a.mode == "Retrieval"]
				if inline:
					content, budget = _inject_inline_files(content, inline, budget)
				if retrieval:
					content = _note_retrieval_files(content, retrieval)
				if query and row.run == last_user_run:
					chunks = retrieve_attachments(query, session=self.name, limit=RETRIEVAL_TOP_K)
					content, budget = _inject_retrieved_chunks(content, chunks, budget)
				message["content"] = content
			messages.append(message)

		memory_block = build_memory_block(self.agent, query=self._latest_user_content())
		if memory_block:
			if messages and messages[0]["role"] == "system":
				messages[0]["content"] = f"{messages[0]['content']}\n\n{memory_block}"
			else:
				messages.insert(0, {"role": "system", "content": memory_block})
		return messages

	def _latest_user_run(self) -> str | None:
		for row in reversed(self.messages):
			if row.role == "user":
				return row.run
		return None

	def _latest_user_content(self) -> str:
		for row in reversed(self.messages):
			if row.role == "user":
				return row.content or ""
		return ""

	def _group_attachments_by_run(self) -> dict[str, list[Any]]:
		grouped: dict[str, list[Any]] = {}
		for attachment in self.attachments:
			grouped.setdefault(attachment.run, []).append(attachment)
		return grouped

	def _assert_not_blocked(self) -> None:
		blocking = frappe.db.get_value(
			"Flow Run",
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
				"Flow Run",
				blocking.name,
				{"status": "Failed", "error": "Run abandoned: stream ended without completing."},
			)
			return
		frappe.throw(
			_("This session already has a run in progress."),
			title=_("Run In Progress"),
		)


def _delete_attachment_files(sessions: list[str]) -> None:
	"""Delete the uploaded File docs attached to these sessions. Per-doc (not bulk SQL)
	so File.on_trash runs to remove the on-disk content, and best-effort so one failure
	never aborts the purge."""
	files = frappe.get_all("Flow Session Attachment", filters={"parent": ["in", sessions]}, pluck="file")
	for file in set(filter(None, files)):
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


def _embeddings_configured() -> bool:
	"""Whether an embedding model is set, i.e. retrieval mode is available."""
	return bool(
		frappe.get_cached_value("Flow Knowledge Settings", "Flow Knowledge Settings", "embedding_model")
	)


def _route_attachment(text: str | None, threshold: int, embeddings_on: bool) -> str:
	"""Inline a file that fits; route an oversized one to retrieval when embeddings are
	available, else keep it Inline (it is truncated to fit at prompt-build time)."""
	if len(text or "") <= threshold:
		return "Inline"
	return "Retrieval" if embeddings_on else "Inline"


def _row_to_message(row) -> dict[str, Any]:
	"""Convert a stored transcript row to an OpenAI-format message dict."""
	if row.role == "tool":
		return {"role": "tool", "tool_call_id": row.tool_call_id, "content": row.content or ""}
	message: dict[str, Any] = {"role": row.role, "content": row.content}
	if row.tool_calls:
		message["tool_calls"] = json.loads(row.tool_calls)
	return message


def _inject_inline_files(content: str | None, attachments: list[Any], budget: int) -> tuple[str, int]:
	"""Append inline files' full text to a user message, clamped to the shared `budget`.
	Returns the augmented content and the remaining budget."""
	blocks = []
	for a in attachments:
		text, truncated = _clamp(a.extracted_text or "", budget)
		budget -= len(text)
		marker = _("\n\n[File truncated to fit the context window.]") if truncated else ""
		blocks.append(f"--- File: {a.file_name} ---\n{text}{marker}\n--- End of file: {a.file_name} ---")
	body = f"{_('The user attached the following file(s):')}\n\n" + "\n\n".join(blocks)
	return (f"{content}\n\n{body}" if content else body), budget


def _note_retrieval_files(content: str | None, attachments: list[Any]) -> str:
	"""Mark where large (retrieval-mode) files were attached, without their bulk. Their
	relevant excerpts are injected on the latest turn rather than inline here."""
	names = ", ".join(a.file_name for a in attachments)
	note = _("The user attached file(s) (large; relevant excerpts shown below): {0}").format(names)
	return f"{content}\n\n{note}" if content else note


def _inject_retrieved_chunks(
	content: str | None, chunks: list[dict[str, Any]], budget: int
) -> tuple[str, int]:
	"""Append retrieved excerpts to the latest user message, within the remaining budget."""
	blocks = []
	for chunk in chunks:
		text, _truncated = _clamp(chunk["content"], budget)
		if not text:
			break
		budget -= len(text)
		blocks.append(text)
	if not blocks:
		return content or "", budget
	body = f"{_('Relevant excerpts from the attached file(s):')}\n\n" + "\n\n---\n\n".join(blocks)
	return (f"{content}\n\n{body}" if content else body), budget


def _clamp(text: str, limit: int) -> tuple[str, bool]:
	"""Return (text capped at `limit` chars, was_truncated)."""
	if limit <= 0:
		return "", bool(text)
	if len(text) <= limit:
		return text, False
	return text[:limit], True


def derive_title(text: str) -> str:
	"""Pick a short title from a user message. Single line, capped at TITLE_MAX_LENGTH."""
	cleaned = " ".join((text or "").split())
	if len(cleaned) <= TITLE_MAX_LENGTH:
		return cleaned
	return cleaned[: TITLE_MAX_LENGTH - 1].rstrip() + "…"
