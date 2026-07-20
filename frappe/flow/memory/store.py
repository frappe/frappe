# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Vectorless LanceDB FTS index over Flow Agent Memory rows.

The Flow Agent Memory doctype is the source of truth; this table holds a
disposable copy for BM25 keyword search once memories outgrow the inject-all
cap. No embeddings — search is full-text only. All operations are best-effort: an index failure
must never block a memory write, and a search failure degrades to recency
in the caller.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import frappe
import lancedb
import pyarrow as pa

from flow.knowledge.store import db_path

if TYPE_CHECKING:
	from flow.flow.doctype.flow_agent_memory.flow_agent_memory import FlowAgentMemory

TABLE_NAME = "memories"
# The FTS-indexed field holds content + keywords.
FTS_FIELD = "search_text"


def _search_text(doc: FlowAgentMemory) -> str:
	content = (doc.content or "").strip()
	keywords = (doc.keywords or "").strip()
	return f"{content}\n{keywords}" if keywords else content


def sync(doc: FlowAgentMemory) -> None:
	"""Upsert an Active memory into the index; drop it for any other status."""
	try:
		table = _table()
		table.delete(f"id = {_quote(doc.name)}")
		if doc.status == "Active":
			table.add(
				[
					{
						"id": doc.name,
						"agent": doc.agent or "",
						"scope": doc.scope or "",
						"user": doc.user or "",
						"search_text": _search_text(doc),
					}
				]
			)
			_ensure_fts_index(table)
	except Exception:
		frappe.log_error(title="Agent memory index sync failed")


def remove(name: str) -> None:
	try:
		db = lancedb.connect(db_path())
		if TABLE_NAME in db.list_tables().tables:
			db.open_table(TABLE_NAME).delete(f"id = {_quote(name)}")
	except Exception:
		frappe.log_error(title="Agent memory index cleanup failed")


def search(query: str, *, agent: str, user: str, limit: int) -> list[str]:
	"""Names of the best keyword matches among `agent`'s shared memories and `user`'s
	personal ones, most relevant first. Empty on failure — the caller falls back to recency."""
	try:
		db = lancedb.connect(db_path())
		if TABLE_NAME not in db.list_tables().tables:
			return []
		table = db.open_table(TABLE_NAME)
		if table.count_rows() == 0:
			return []
		_ensure_fts_index(table)
		scope = f"agent = {_quote(agent)} AND (scope = 'Agent' OR user = {_quote(user)})"
		rows = table.search(query, query_type="fts").where(scope, prefilter=True).limit(limit).to_list()
		return [row["id"] for row in rows]
	except Exception:
		frappe.log_error(title="Agent memory search failed")
		return []


def drop_table() -> None:
	"""Drop the whole memories index. Disposable — rebuildable from the doctype rows.
	Path is db_path()-scoped, so under `frappe.flags.in_test` it only touches lancedb_test."""
	db = lancedb.connect(db_path())
	if TABLE_NAME in db.list_tables().tables:
		db.drop_table(TABLE_NAME)


def _table():
	db = lancedb.connect(db_path())
	if TABLE_NAME in db.list_tables().tables:
		return db.open_table(TABLE_NAME)
	schema = pa.schema(
		[
			pa.field("id", pa.string()),
			pa.field("agent", pa.string()),
			pa.field("scope", pa.string()),
			pa.field("user", pa.string()),
			pa.field(FTS_FIELD, pa.string()),
		]
	)
	return db.create_table(TABLE_NAME, schema=schema, exist_ok=True)


def _ensure_fts_index(table) -> None:
	"""Create the full-text index once. LanceDB's native FTS automatically
	searches rows added after index creation, so no reindexing on write."""
	if any(str(index.index_type) == "FTS" for index in table.list_indices()):
		return
	table.create_fts_index(FTS_FIELD, replace=True)


def _quote(value: str) -> str:
	"""Quote a string for a LanceDB SQL predicate (single quotes doubled)."""
	if not isinstance(value, str):
		raise ValueError(f"Expected string filter value, got {type(value).__name__}")
	escaped = value.replace("'", "''")
	return f"'{escaped}'"
