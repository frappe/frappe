# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""LanceDB index over Flow Agent Memory rows, used to find the memories relevant to a message.

The rows are the source of truth. The table holds the scoping columns, the content (full-text
indexed) and a vector when an embedding model is configured. It is rebuilt from the rows
whenever its shape no longer matches the settings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pyarrow as pa

import frappe
from frappe.flow.knowledge.store import _connect, _ensure_fts_index, _quote

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
	table = ensure_table()
	rows = _rows(table, [doc]) if doc.status == "Active" else []
	table.delete(f"id = {_quote(doc.name)}")
	if rows:
		table.add(rows)
		_ensure_fts_index(table)


def remove(name: str) -> None:
	try:
		db = _connect()
		if TABLE_NAME in db.list_tables().tables:
			db.open_table(TABLE_NAME).delete(f"id = {_quote(name)}")
	except Exception:
		frappe.log_error(title="Agent memory index cleanup failed")


def rename_agent(old: str, new: str) -> None:
	"""Move a renamed agent's memories to its new name."""
	db = _connect()
	if TABLE_NAME in db.list_tables().tables:
		db.open_table(TABLE_NAME).update(where=f"agent = {_quote(old)}", values={"agent": new})


def search(query: str, *, agent: str, user: str) -> list[str]:
	"""Names of the memories relevant to `query`, best first, within `agent` and `user`'s scope."""
	table = ensure_table()
	scope = f"agent = {_quote(agent)} AND (scope = 'Agent' OR user = {_quote(user)})"
	in_scope = table.count_rows(scope)
	if not in_scope:
		return []
	_ensure_fts_index(table)
	keyword = table.search(query, query_type="fts").where(scope, prefilter=True).limit(TOP_K).to_list()
	if "vector" not in table.schema.names:
		return [row["id"] for row in keyword]

	from frappe.flow.knowledge.embedder import embed_texts

	(vector,) = embed_texts([query])
	keyword_ids = {row["id"] for row in keyword}
	nearest = (
		table.search(vector, vector_column_name="vector")
		.distance_type("cosine")
		.where(scope, prefilter=True)
		.limit(in_scope)
		.to_list()
	)
	scored = []
	for row in nearest:
		score = 1.0 - row["_distance"] + (KEYWORD_BONUS if row["id"] in keyword_ids else 0.0)
		if score >= MIN_SCORE:
			scored.append((score, row["id"]))
	scored.sort(reverse=True)
	return [name for _score, name in scored[:TOP_K]]


def drop_table() -> None:
	"""Drop the index; the next write or search rebuilds it."""
	db = _connect()
	if TABLE_NAME in db.list_tables().tables:
		db.drop_table(TABLE_NAME)


def ensure_table():
	"""Open the memories table, recreating it from the rows when its shape no longer
	matches the settings (embedding model or vector width)."""
	db = _connect()
	schema = _schema()
	if TABLE_NAME in db.list_tables().tables:
		table = db.open_table(TABLE_NAME)
		if table.schema.equals(schema, check_metadata=True):
			return table
		db.drop_table(TABLE_NAME)
	table = db.create_table(TABLE_NAME, schema=schema)
	docs = frappe.get_all(
		"Flow Agent Memory",
		filters={"status": "Active"},
		fields=["name", "agent", "scope", "user", "content"],
	)
	if docs:
		table.add(_rows(table, docs))
		_ensure_fts_index(table)
	return table


def _schema() -> pa.Schema:
	settings = frappe.get_cached_doc("Flow Knowledge Settings")
	fields = [
		pa.field("id", pa.string()),
		pa.field("agent", pa.string()),
		pa.field("scope", pa.string()),
		pa.field("user", pa.string()),
		pa.field("content", pa.string()),
	]
	model = ""
	if settings.embedding_model and settings.embedding_dimension:
		# by id and server, so a rename keeps the index
		model_id, base_url = frappe.get_cached_value(
			"Flow Model", settings.embedding_model, ["model_id", "base_url"]
		)
		model = f"{model_id} {base_url}" if base_url else model_id
		fields.append(pa.field("vector", pa.list_(pa.float32(), int(settings.embedding_dimension))))
	return pa.schema(fields, metadata={"embedding_model": model})


def _rows(table, docs: list[Any]) -> list[dict[str, Any]]:
	rows = [
		{
			"id": doc.name,
			"agent": doc.agent,
			"scope": doc.scope,
			"user": doc.user or "",
			"content": doc.content,
		}
		for doc in docs
	]
	if "vector" in table.schema.names:
		from frappe.flow.knowledge.embedder import embed_texts

		for row, vector in zip(rows, embed_texts([row["content"] for row in rows]), strict=True):
			row["vector"] = vector
	return rows
