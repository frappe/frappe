# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""SQLite index over Flow Agent Memory rows, used to find the memories relevant to a message.

The rows are the source of truth. The table holds the scoping columns, the content (full-text
indexed) and a vector when an embedding model is configured. It is rebuilt from the rows
whenever its shape no longer matches the settings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import frappe
from frappe.flow.knowledge.store import (
	_connect,
	_create_table,
	_drop_table,
	_keyword_search,
	_placeholders,
	_shape,
	_vector_bytes,
)

if TYPE_CHECKING:
	from frappe.flow.doctype.flow_agent_memory.flow_agent_memory import FlowAgentMemory

TABLE_NAME = "memories"
# A turn gets at most TOP_K memories scoring at least MIN_SCORE: cosine similarity, plus
# KEYWORD_BONUS when the memory is also a keyword hit.
TOP_K = 8
MIN_SCORE = 0.3
KEYWORD_BONUS = 0.1


def sync(doc: FlowAgentMemory) -> None:
	"""Upsert an Active memory; drop it for any other status. A failure fails the save."""
	dimension = ensure_table()
	# embed first, so a failed call keeps the old row
	rows = _rows([doc], dimension) if doc.status == "Active" else []
	with _connect(write=True) as db:
		db.execute(f"delete from {TABLE_NAME} where id = ?", (doc.name,))
		_insert(db, rows)


def remove(name: str) -> None:
	try:
		with _connect(write=True) as db:
			if _shape(db, TABLE_NAME) is not None:
				db.execute(f"delete from {TABLE_NAME} where id = ?", (name,))
	except Exception:
		frappe.log_error(title="Agent memory index cleanup failed")


def rename_agent(old: str, new: str) -> None:
	"""Move a renamed agent's memories to its new name."""
	with _connect(write=True) as db:
		if _shape(db, TABLE_NAME) is not None:
			db.execute(f"update {TABLE_NAME} set agent = ? where agent = ?", (new, old))


def make_personal(names: list[str], user: str) -> None:
	"""Move shared memories to `user`'s own, keeping their vectors."""
	if not names:
		return
	with _connect(write=True) as db:
		if _shape(db, TABLE_NAME) is not None:
			db.execute(
				f"update {TABLE_NAME} set scope = 'User', user = ? where id in ({_placeholders(names)})",
				[user, *names],
			)


def search(query: str, *, agent: str, user: str) -> list[str]:
	"""Names of the memories relevant to `query`, best first, within `agent` and `user`'s scope."""
	dimension = ensure_table()
	scope = "agent = ? and (scope = 'Agent' or user = ?)"
	with _connect() as db:
		if not db.execute(f"select 1 from {TABLE_NAME} where {scope} limit 1", (agent, user)).fetchone():
			return []
		keyword = _keyword_search(db, TABLE_NAME, scope, [agent, user], query, TOP_K, column="id")
	if not dimension:
		return keyword

	from frappe.flow.knowledge.embedder import embed_texts

	(vector,) = embed_texts([query])
	with _connect() as db:
		nearest = db.execute(
			# a zero vector has no distance
			f"select id, vec_distance_cosine(vector, ?) as distance from {TABLE_NAME} "
			f"where {scope} and distance is not null",
			(_vector_bytes(vector), agent, user),
		).fetchall()
	scored = []
	for name, distance in nearest:
		score = 1.0 - distance + (KEYWORD_BONUS if name in keyword else 0.0)
		if score >= MIN_SCORE:
			scored.append((score, name))
	scored.sort(reverse=True)
	return [name for _score, name in scored[:TOP_K]]


def drop_table() -> None:
	"""Drop the index; the next write or search rebuilds it."""
	with _connect(write=True) as db:
		_drop_table(db, TABLE_NAME)


def ensure_table() -> int:
	"""Rebuild the table from the rows if the embedding model or width changed.
	Returns the vector width, 0 for none."""
	dimension, shape = _dimension_and_shape()
	with _connect() as db:
		if _shape(db, TABLE_NAME) == shape:
			return dimension

	docs = frappe.get_all(
		"Flow Agent Memory",
		filters={"status": "Active"},
		fields=["name", "agent", "scope", "user", "content"],
	)
	rows = _rows(docs, dimension)
	with _connect(write=True) as db:
		_drop_table(db, TABLE_NAME)
		_create_table(
			db,
			TABLE_NAME,
			"seq integer primary key, id text unique, agent text, scope text, user text",
			dimension,
			shape,
		)
		db.execute(f"create index {TABLE_NAME}_agent on {TABLE_NAME}(agent)")
		_insert(db, rows)
	return dimension


def _dimension_and_shape() -> tuple[int, str]:
	"""Vector width (0 without a model) and the marker the table is checked against."""
	settings = frappe.get_cached_doc("Flow Knowledge Settings")
	if not (settings.embedding_model and settings.embedding_dimension):
		return 0, "0"
	# by id and server, so a rename keeps the index
	model_id, base_url = frappe.get_cached_value(
		"Flow Model", settings.embedding_model, ["model_id", "base_url"]
	)
	dimension = int(settings.embedding_dimension)
	return dimension, f"{dimension} {model_id} {base_url or ''}".strip()


def _rows(docs: list[Any], dimension: int) -> list[tuple]:
	vectors = [None] * len(docs)
	if dimension and docs:
		from frappe.flow.knowledge.embedder import embed_texts

		vectors = [_vector_bytes(vector) for vector in embed_texts([doc.content for doc in docs])]
	return [
		(doc.name, doc.agent, doc.scope, doc.user or "", doc.content, vector)
		for doc, vector in zip(docs, vectors, strict=True)
	]


def _insert(db, rows: list[tuple]) -> None:
	db.executemany(
		f"insert into {TABLE_NAME}(id, agent, scope, user, content, vector) values (?, ?, ?, ?, ?, ?)", rows
	)
