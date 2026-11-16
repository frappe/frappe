# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Ephemeral, session-scoped vector store for oversized chat attachments.

Separate from the curated KB store (store.py) so chat files never surface in
agent knowledge-base search. Reads are scoped by `session`; the session-owner
check in load_session() is the authorization boundary, enforced before any
search runs. The `extracted_text` column is the source of truth; this index is
disposable and rebuildable.
"""

from __future__ import annotations

from typing import Any

from frappe.flow.knowledge.store import (
	_connect,
	_create_table,
	_drop_table,
	_placeholders,
	_search,
	_shape,
	_vector_bytes,
)

TABLE_NAME = "chat_attachment_chunks"
MAX_SEARCH_LIMIT = 50


def ensure_table(dimension: int) -> None:
	"""Create the chunks table for the given vector width if it is missing.

	On a width mismatch (the embedding model changed) the table is dropped and
	recreated — chat chunks are ephemeral and rebuildable, so they are not worth
	preserving across an embedding-model change.
	"""
	if not isinstance(dimension, int) or dimension < 1:
		raise ValueError(f"Invalid embedding dimension: {dimension!r}")

	with _connect(write=True) as db:
		if _shape(db, TABLE_NAME) == str(dimension):
			return
		_drop_table(db, TABLE_NAME)
		_create_table(db, TABLE_NAME, "id integer primary key, session text, attachment text", dimension)
		db.execute(f"create index {TABLE_NAME}_session on {TABLE_NAME}(session)")


def add(session: str, attachment: str, chunks: list[str], vectors: list[list[float]]) -> None:
	"""Insert one attachment's chunks. The table must already exist (ensure_table)."""
	if len(chunks) != len(vectors):
		raise ValueError(f"chunks/vectors length mismatch: {len(chunks)} != {len(vectors)}")
	if not chunks:
		return
	with _connect(write=True) as db:
		db.executemany(
			f"insert into {TABLE_NAME}(session, attachment, content, vector) values (?, ?, ?, ?)",
			[
				(session, attachment, content, _vector_bytes(vector))
				for content, vector in zip(chunks, vectors, strict=True)
			],
		)


def search(
	vector: list[float], *, session: str, text: str | None = None, limit: int = 8
) -> list[dict[str, Any]]:
	"""Best-matching chunks within one session, most relevant first.

	With `text`, runs hybrid search (vector + full-text, rank-fused); otherwise
	vector-only. Returns [{attachment, content, score}] with higher score = better match. Scoping
	to `session` is mandatory — there is no unscoped search.
	"""
	if not session:
		raise ValueError("search requires a session scope")
	limit = max(1, min(int(limit), MAX_SEARCH_LIMIT))

	with _connect() as db:
		if _shape(db, TABLE_NAME) is None:
			return []
		hits = _search(db, TABLE_NAME, "attachment, content", "session = ?", [session], vector, text, limit)
	return [
		{"attachment": attachment, "content": content, "score": score} for attachment, content, score in hits
	]


def delete(*, session: str | list[str] | None = None, attachment: str | None = None) -> None:
	"""Delete rows matching ALL given criteria. At least one is required.
	`session` may be a single id or a list of ids (an empty list is a no-op)."""
	if session is None and attachment is None:
		raise ValueError("delete() requires session and/or attachment")
	if isinstance(session, list) and not session:
		return

	conditions, values = [], []
	if session is not None:
		sessions = [session] if isinstance(session, str) else session
		conditions.append(f"session in ({_placeholders(sessions)})")
		values.extend(sessions)
	if attachment is not None:
		conditions.append("attachment = ?")
		values.append(attachment)
	with _connect(write=True) as db:
		if _shape(db, TABLE_NAME) is not None:
			db.execute(f"delete from {TABLE_NAME} where {' and '.join(conditions)}", values)


def drop_table() -> None:
	with _connect(write=True) as db:
		_drop_table(db, TABLE_NAME)


def _table_exists() -> bool:
	with _connect() as db:
		return _shape(db, TABLE_NAME) is not None
