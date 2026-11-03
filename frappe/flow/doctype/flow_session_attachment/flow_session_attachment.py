# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Files sent with a chat turn: validated at upload time, when text is also extracted and
an image is OCRed only for a text-only model, then folded into that turn's flow server
message on send, as a block naming the saved File. Earlier turns are never rewritten, so a
file travels with the turn it was sent on and the prompt prefix stays cacheable."""

from __future__ import annotations

import csv
import io
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
# Each turn gets a fixed fraction of the model's total context for attachment text.
# This deliberately ignores current transcript occupancy: the daemon compacts history.
# When a set does not fit, the largest files move to retrieval first so only the minimum
# necessary amount of content goes through RAG.
DEFAULT_CONTEXT_WINDOW = 128000
CHARS_PER_TOKEN = 4
INLINE_TEXT_FRACTION = 0.5
RETRIEVAL_TOP_K = 8
TRUNCATED = "[File truncated to fit the context window.]"
# Text a turn pastes in full when the agent can read the rest with `read_attachment`; it is
# re-sent on every later call of the session. Other files go as a preview of the saved File.
# A table is referenced sooner: it is for tools such as Data Import, prose for the model to read.
PASTE_LIMIT = 32000
TABLE_PASTE_LIMIT = 8000
PREVIEW_ROWS = 5
PREVIEW_CHARS = 1000
READ_LIMIT = 1000
READ_CHAR_LIMIT = 20000
TABLE_EXTENSIONS = {"csv", "tsv", "xlsx"}
IMPORT_EXTENSIONS = {"csv", "xlsx"}
ATTACHMENT_DOCTYPE = "Flow Session"


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
	"""Fold `files` into one turn, each text file as a block naming its File and URL: the
	smallest pasted in full while they fit the paste budget, the rest previewed. Text over
	the turn's budget is also indexed and excerpted for `input`; later turns search it with
	`search_attachments`. Images go as uploads when the model can see them, else as OCR text.
	A file in the block is recorded as Inline, pasted or previewed."""
	files = list(dict.fromkeys(files))
	if len(files) > MAX_ATTACHMENTS:
		frappe.throw(
			_("Attach at most {0} files per message.").format(MAX_ATTACHMENTS), title=_("Too Many Files")
		)
	budget = _inline_text_budget(session)
	from frappe.flow.tools.builtins import ATTACHMENT_READ_SLUG, builtin_name

	readable = frappe.get_cached_doc("Flow Agent", session.agent).has_tool(builtin_name(ATTACHMENT_READ_SLUG))
	paste_budget = min(PASTE_LIMIT, budget) if readable else budget
	vision = _model_sees_images(_session_model(session))
	embeddings_on = _embeddings_configured()
	turn = Turn(message=input)
	text_files: list[tuple[dict[str, Any], str]] = []
	file_docs: dict[str, Document] = {}
	for file in files:
		data, file_doc = load_attachment(file)
		file_docs[file] = file_doc
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
	tables = {file for file, file_doc in file_docs.items() if _extension(file_doc) in TABLE_EXTENSIONS}
	pasted = _pasted_files(text_files, paste_budget, retrieval, tables if readable else set())
	indexed = []
	try:
		existing = {attachment.file for attachment in session.attachments if attachment.mode == "Retrieval"}
		remaining = paste_budget - sum(len(text) for row, text in text_files if row["file"] in pasted)
		for row, text in text_files:
			file, file_doc = row["file"], file_docs[row["file"]]
			mode = "Retrieval" if file in retrieval else "Inline"
			if mode == "Retrieval" and file not in existing:
				_index(session.name, file, text)
				indexed.append(file)
			if file in pasted:
				body = _csv_lines(_table_rows(file_doc)) if _extension(file_doc) == "xlsx" else text
			elif readable or mode == "Retrieval":
				body = _preview(file_doc, text, readable)
			else:  # an agent that cannot read the rest gets as much as fits, as before read_attachment
				body = f"{text[:remaining]}\n{TRUNCATED}"
				remaining = 0
			turn.message += "\n" + _file_block(file_doc, body)
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
	extension = _extension(file_doc)
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


def _pasted_files(
	text_files: list[tuple[dict[str, Any], str]], budget: int, skip: set[str], tables: set[str]
) -> set[str]:
	"""Files pasted in full: the smallest first, while their text fits the budget."""
	pasted: set[str] = set()
	for row, text in sorted(text_files, key=lambda item: len(item[1])):
		if row["file"] in skip or (row["file"] in tables and len(text) > TABLE_PASTE_LIMIT):
			continue
		if len(text) > budget:
			break
		pasted.add(row["file"])
		budget -= len(text)
	return pasted


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


def _file_block(file_doc: Document, body: str) -> str:
	"""The flow server's own marker for a text attachment, with the saved File it came from,
	so the model can pass its URL to a tool. Model-facing, so not translated."""
	attrs = {
		"name": file_doc.file_name,
		"file": file_doc.name,
		"url": file_doc.file_url,
		"size": _size_text(file_doc.file_size),
	}
	head = " ".join(f'{key}="{_xml_attr(str(value or ""))}"' for key, value in attrs.items())
	return f"<file {head}>\n{body}\n</file>"


def _preview(file_doc: Document, text: str, readable: bool) -> str:
	"""What the model sees of a file not pasted in full: its shape and its start."""
	more = " Read more with read_attachment." if readable else ""
	rows = _table_rows(file_doc)
	if rows is not None:
		header, data = rows[:1], rows[1:]
		columns = ", ".join(str(cell) for cell in (header[0] if header else []))
		shown = header + data[:PREVIEW_ROWS]
		extension = _extension(file_doc)
		hint = (
			" To import it, pass its url to Data Import's import_file."
			if extension in IMPORT_EXTENSIONS
			else ""
		)
		sheet = " (the workbook's active sheet, which Data Import reads)" if extension == "xlsx" else ""
		return (
			f"Saved as a File, not shown in full.{hint}\n"
			f"Table{sheet}: {len(data):,} rows, columns: {columns}\n"
			f"{_csv_lines(shown)}\n"
			f"[Preview: the header and the first {min(PREVIEW_ROWS, len(data))} rows.{more}]"
		)
	lines = text.count("\n") + 1
	return (
		f"Saved as a File, not shown in full: {len(text):,} characters, {lines:,} lines.\n"
		f"{text[:PREVIEW_CHARS]}\n"
		f"[Preview: the first {min(PREVIEW_CHARS, len(text)):,} characters.{more}]"
	)


def _table_rows(file_doc: Document) -> list[list[Any]] | None:
	"""A table's rows as Data Import reads them (an XLSX's active sheet); None for other files,
	and for a table the reader rejects, which then goes as text."""
	from frappe.utils.csvutils import read_csv_content
	from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file

	extension = _extension(file_doc)
	if extension not in TABLE_EXTENSIONS:
		return None
	content = file_doc.get_content()
	try:
		if extension == "xlsx":
			rows = read_xlsx_file_from_attached_file(fcontent=content, read_only=True) or []
		else:
			rows = read_csv_content(content, delimiter="\t" if extension == "tsv" else None)
	except Exception:
		return None
	return [row for row in rows if any(cell not in (None, "") for cell in row)]


def _csv_lines(rows: list[list[Any]]) -> str:
	out = io.StringIO()
	csv.writer(out, lineterminator="\n").writerows(
		["" if cell is None else cell for cell in row] for row in rows
	)
	return out.getvalue().rstrip("\n")


def _extension(file_doc: Document) -> str:
	return os.path.splitext(file_doc.file_name or file_doc.file_url or "")[1].lower().lstrip(".")


def _size_text(size: int | None) -> str:
	kb = (size or 0) / 1024
	return f"{kb / 1024:.1f} MB" if kb >= 1024 else f"{max(1, round(kb))} KB"


def read_attachment(session: str, file: str | None, offset: int = 1, limit: int | None = None) -> Any:
	"""Lines `offset`.. of a File attached to `session`, as the user, capped in characters; a
	line longer than the cap counts as several. A table's rows are CSV lines, its header line 1.
	Without `file`, the session's files."""
	held = frappe.cache.get_value(_sending_key(session)) or []
	if not file:
		return frappe.get_list(
			"File",
			filters={"name": ["in", _session_files(session, held)]},
			fields=["name as file", "file_name", "file_url as url"],
			order_by="creation asc",
		)
	if not frappe.db.exists("File", file):  # the model may name the file as the user does
		file = _session_file_named(session, held, file) or file
	file_doc = _readable_file(file)
	attached = (file_doc.attached_to_doctype, file_doc.attached_to_name) == (ATTACHMENT_DOCTYPE, session)
	if not attached and file not in held:
		frappe.throw(_("{0} is not attached to this chat.").format(file), frappe.PermissionError)
	rows = _table_rows(file_doc)
	if rows is not None:
		lines = [_csv_lines([row]) for row in rows]
	else:
		text = _attachment_text(session, file_doc)
		if text is None:
			frappe.throw(_("{0} is an image; it has no text to read.").format(file_doc.file_name))
		lines = text.split("\n")
	lines = [
		line[i : i + READ_CHAR_LIMIT] for line in lines for i in range(0, max(len(line), 1), READ_CHAR_LIMIT)
	]
	start = max(1, cint(offset)) - 1
	end = start + max(1, min(cint(limit) or READ_LIMIT, READ_LIMIT))
	out, size = [], 0
	for line in lines[start:end]:
		if out and size + len(line) > READ_CHAR_LIMIT:
			break
		out.append(line)
		size += len(out[-1]) + 1
	shown = start + len(out)
	if not out:
		return f"[Past the end: {len(lines)} lines.]"
	note = f"[Lines {start + 1}-{shown} of {len(lines)}."
	note += f" Continue at offset {shown + 1}.]" if shown < len(lines) else "]"
	return "\n".join([*out, note])


def _session_file_named(session: str, held: list[str], file_name: str) -> str | None:
	files = frappe.get_all(
		"File",
		filters={"name": ["in", _session_files(session, held)], "file_name": file_name},
		pluck="name",
		order_by="creation desc",
		limit=1,
	)
	return files[0] if files else None


def _session_files(session: str, held: list[str]) -> list[str]:
	"""The Files attached to `session`, and those of its turn being sent."""
	attached = frappe.get_all(
		"File", filters={"attached_to_doctype": ATTACHMENT_DOCTYPE, "attached_to_name": session}, pluck="name"
	)
	return [*attached, *held] or [""]


def hold_sent_files(session: str, files: list[str]) -> None:
	"""Let `read_attachment` see a turn's Files before the request that sends them commits
	their claim on the session: the turn's tool calls come in requests of their own."""
	if files:
		held = frappe.cache.get_value(_sending_key(session)) or []
		frappe.cache.set_value(_sending_key(session), [*held, *files], expires_in_sec=CACHE_TTL)


def release_sent_files(session: str) -> None:
	frappe.cache.delete_value(_sending_key(session))


def _sending_key(session: str) -> str:
	return f"{CACHE_PREFIX}:sending:{session}"


def _attachment_text(session: str, file_doc: Document) -> str | None:
	"""The text sent for this File: its saved row's, else the extraction staged at upload or a
	fresh one (the first turn's tool calls can come before the rows are saved)."""
	text = frappe.db.get_value(
		"Flow Session Attachment", {"parent": session, "file": file_doc.name}, "extracted_text"
	)
	if text:
		return text
	data = staged_attachment(file_doc.name) or _extract(file_doc)
	if data["extracted_text"] is not None:
		return data["extracted_text"]
	return data.get("ocr_text")


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
