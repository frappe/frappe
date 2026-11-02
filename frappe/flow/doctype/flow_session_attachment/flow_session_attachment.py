# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Files sent with a chat turn: validated at upload time, when text is also extracted and
an image is OCRed only for a text-only model, then folded into that turn's flow server
message on send. Earlier turns are never rewritten, so a file travels with the turn it was
sent on and the prompt prefix stays cacheable."""

from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from flow_harness.session.attachments import MAX_ATTACHMENTS_PER_MESSAGE

import frappe
from frappe import _
from frappe.flow.knowledge.extract import FILE_EXTENSIONS, IMAGE_EXTENSIONS, extract_file
from frappe.model.document import Document
from frappe.utils import cint

if TYPE_CHECKING:
	from frappe.flow.doctype.flow_session.flow_session import FlowSession

CACHE_PREFIX = "chat_attachment"
CACHE_TTL = 3600

MAX_ATTACHMENTS = MAX_ATTACHMENTS_PER_MESSAGE
# Each turn gets a fixed fraction of the model's total context for exact attachment text.
# This deliberately ignores current transcript occupancy: the daemon compacts history.
# When a set does not fit, the largest files move to retrieval first so smaller files stay
# exact and only the minimum necessary amount of content goes through RAG.
DEFAULT_CONTEXT_WINDOW = 128000
CHARS_PER_TOKEN = 4
INLINE_TEXT_FRACTION = 0.5
RETRIEVAL_TOP_K = 8
TRUNCATED = "[File truncated to fit the context window.]"


class FlowSessionAttachment(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		extracted_text: DF.LongText | None
		file: DF.Link
		file_name: DF.Data | None
		file_size: DF.Int
		mode: DF.Literal["Inline", "Retrieval", "Image"]
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		run: DF.Link | None
	# end: auto-generated types

	pass


@dataclass
class Turn:
	"""What a chat turn sends: the message with its file text folded in, the images the
	flow server gets as uploads, and the attachment rows to record against the run."""

	message: str
	images: list[tuple[str, bytes, str]] = field(default_factory=list)
	attachment_rows: list[dict[str, Any]] = field(default_factory=list)
	indexed_files: list[str] = field(default_factory=list)


def build_turn(session: FlowSession, input: str, files: list[str]) -> Turn:
	"""Fold `files` into one turn. Text that fits is inlined; larger text is indexed and
	excerpted for `input`; later turns search it with `search_attachments`. Images go as
	uploads when the model can see them, else as OCR text."""
	files = list(dict.fromkeys(files))
	if len(files) > MAX_ATTACHMENTS:
		frappe.throw(
			_("Attach at most {0} files per message.").format(MAX_ATTACHMENTS), title=_("Too Many Files")
		)
	budget = _inline_text_budget(session)
	vision = _model_sees_images(_session_model(session))
	embeddings_on = _embeddings_configured()
	turn = Turn(message=input)
	text_files: list[tuple[dict[str, Any], str]] = []
	for file in files:
		data, file_doc = load_attachment(file)
		row = {key: data[key] for key in ("file", "file_name", "file_size")}
		text = data["extracted_text"]
		if text is None:
			if vision:
				mime = mimetypes.guess_type(data["file_name"])[0] or "application/octet-stream"
				turn.images.append((data["file_name"], file_doc.get_content(), mime))
				turn.attachment_rows.append({**row, "mode": "Image"})
				continue
			text = data.get("ocr_text")
			if text is None:
				text = extract_file(file_doc)
			if not text:
				frappe.throw(
					_("No readable text found in {0}.").format(data["file_name"]), title=_("Empty File")
				)
		text_files.append((row, text))

	retrieval = _retrieval_files(text_files, budget) if embeddings_on else set()
	indexed = []
	try:
		existing = {attachment.file for attachment in session.attachments if attachment.mode == "Retrieval"}
		remaining = budget
		for row, text in text_files:
			file = row["file"]
			mode = "Retrieval" if file in retrieval else "Inline"
			if mode == "Retrieval":
				if file not in existing:
					_index(session.name, file, text)
					indexed.append(file)
				turn.message += "\n" + _("[Attached file: {0} (large; relevant excerpts follow)]").format(
					row["file_name"]
				)
			else:
				turn.message += "\n" + _file_block(row["file_name"], text, remaining)
				remaining = max(0, remaining - len(text))
			turn.attachment_rows.append({**row, "mode": mode, "extracted_text": text})

		if retrieval:
			turn.message += _excerpts(input, session.name)
	except Exception:
		cleanup_indexed_files(session.name, indexed)
		raise
	turn.indexed_files = indexed
	return turn


def stage_attachment(file: str, model: str | None = None) -> dict[str, Any]:
	"""Extract at upload time and cache the result, so send need not parse the file again.
	An image is OCRed now only when `model` cannot see it, else on send if still needed.
	Returns lightweight metadata for the composer chip."""
	data, file_doc = load_attachment(file)
	if data["extracted_text"] is None and "ocr_text" not in data and not _model_sees_images(model):
		data["ocr_text"] = extract_file(file_doc)
	frappe.cache.set_value(_cache_key(file), data, expires_in_sec=CACHE_TTL)
	return {"file": data["file"], "file_name": data["file_name"], "file_size": data["file_size"]}


def cleanup_indexed_files(session: str, files: list[str]) -> None:
	"""Best-effort rollback for retrieval files whose turn was not accepted."""
	if not files:
		return
	from frappe.flow.knowledge import attachment_store

	for file in files:
		try:
			attachment_store.delete(session=session, attachment=file)
		except Exception:
			frappe.log_error(title="Chat attachment rollback failed")


def load_attachment(file: str) -> tuple[dict[str, Any], Document]:
	"""A File the caller may read, with its extraction: the one staged at upload, else a
	fresh one. Raises for an unreadable file or an unsupported type. Whether images
	are sent directly or as OCR text, cached or fresh, is decided on send."""
	file_doc = _readable_file(file)
	return staged_attachment(file) or _extract(file_doc), file_doc


def staged_attachment(file: str) -> dict[str, Any] | None:
	"""Read the extraction staged at upload time. None if it has expired."""
	return frappe.cache.get_value(_cache_key(file))


def _readable_file(file: str) -> Document:
	file_doc = frappe.get_doc("File", file)
	if not frappe.has_permission("File", "read", doc=file_doc):
		frappe.throw(_("Not permitted to use this file."), frappe.PermissionError)
	return file_doc


def _extract(file_doc: Document) -> dict[str, Any]:
	extension = os.path.splitext(file_doc.file_name or "")[1].lower().lstrip(".")
	if extension not in FILE_EXTENSIONS:
		frappe.throw(_("Unsupported file type: .{0}").format(extension or "?"), title=_("Unsupported File"))

	text = None if extension in IMAGE_EXTENSIONS else extract_file(file_doc)
	if text == "":
		frappe.throw(_("No readable text found in this file."), title=_("Empty File"))

	return {
		"file": file_doc.name,
		"file_name": file_doc.file_name,
		"file_size": file_doc.file_size,
		"extracted_text": text,
	}


def _cache_key(file: str) -> str:
	return f"{CACHE_PREFIX}:{frappe.session.user}:{file}"


def _inline_text_budget(session: FlowSession) -> int:
	"""Fixed characters available to exact file text, independent of transcript occupancy."""
	model = _session_model(session)
	window = frappe.db.get_value("Flow Model", model, "context_window") or DEFAULT_CONTEXT_WINDOW
	return int(window * CHARS_PER_TOKEN * INLINE_TEXT_FRACTION)


def _model_sees_images(model: str | None) -> bool:
	"""Same rule as the flow server: only a model known to be text-only gets no images."""
	from flow_harness.model.catalog import model_supports_images

	model_id = frappe.db.get_value("Flow Model", model, "model_id") if model else None
	if not model_id:
		return True
	return model_supports_images(model_id) is not False


def _session_model(session: FlowSession) -> str:
	return session.model or frappe.db.get_value("Flow Agent", session.agent, "model")


def _embeddings_configured() -> bool:
	return bool(
		frappe.get_cached_value("Flow Knowledge Settings", "Flow Knowledge Settings", "embedding_model")
	)


def _retrieval_files(text_files: list[tuple[dict[str, Any], str]], budget: int) -> set[str]:
	"""Files that go to retrieval: the largest first, until the rest fit the budget."""
	total = sum(len(text) for _row, text in text_files)
	retrieval: set[str] = set()
	for row, text in sorted(text_files, key=lambda item: len(item[1]), reverse=True):
		if total <= budget:
			break
		retrieval.add(row["file"])
		total -= len(text)
	return retrieval


def _index(session: str, file: str, text: str) -> None:
	"""Replace one file's chunks in the session retrieval index."""
	from frappe.flow.knowledge import attachment_store
	from frappe.flow.knowledge.chunker import chunk_text
	from frappe.flow.knowledge.embedder import embed_texts

	settings = frappe.get_cached_doc("Flow Knowledge Settings")
	try:
		chunks = chunk_text(text, chunk_size=cint(settings.chunk_size), overlap=cint(settings.chunk_overlap))
		vectors = embed_texts(chunks)
		attachment_store.ensure_table(cint(settings.embedding_dimension))
		attachment_store.delete(session=session, attachment=file)
		attachment_store.add(session, file, chunks, vectors)
	except Exception:
		frappe.log_error(title="Chat attachment indexing failed")
		frappe.throw(
			_("Could not index the attached file. Please retry."), title=_("Attachment Indexing Failed")
		)


def _file_block(name: str, text: str, limit: int) -> str:
	"""The flow server's own marker for a text attachment, so inlined files read the same."""
	if len(text) > limit:
		text = f"{text[:limit]}\n{TRUNCATED}"
	return f'<file name="{_xml_attr(name)}">\n{text}\n</file>'


def _excerpts(query: str, session: str) -> str:
	"""The session's best-matching retrieval chunks as a message block; "" when none match."""
	from frappe.flow.knowledge.retriever import retrieve_attachments

	try:
		hits = retrieve_attachments(query, session=session, limit=RETRIEVAL_TOP_K)
	except Exception:
		frappe.log_error(title="Chat attachment search failed")
		frappe.throw(
			_("Could not search the attached files. Please retry."), title=_("Attachment Search Failed")
		)
	if not hits:
		return ""
	lead = _("Relevant excerpts from the attached files:")
	body = "\n---\n".join(hit["content"] for hit in hits)
	return f"\n{lead}\n<excerpts>\n{body}\n</excerpts>"


def _xml_attr(value: str) -> str:
	return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
