# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Site-scoped LanceDB vector store.

MariaDB (Flow Knowledge Chunk) is the source of truth for chunk text and metadata.
This store holds only what search needs: the vector, scoping columns, and a copy
of the content for the full-text index. Row `id` is the chunk's autoincrement name,
so every hit maps back to its MariaDB row. The whole store is disposable — it can
be rebuilt from MariaDB at any time.
"""

from __future__ import annotations

from typing import Any

import frappe
import lancedb
import pyarrow as pa
from frappe import _

TABLE_NAME = "chunks"
FTS_FIELD = "content"
MAX_SEARCH_LIMIT = 100


def db_path() -> str:
	name = "lancedb_test" if frappe.flags.in_test else "lancedb"
	return frappe.get_site_path("private", "files", name)


def _connect():
	return lancedb.connect(db_path())


def table_exists() -> bool:
	return TABLE_NAME in _connect().list_tables().tables


def _vector_dim(table) -> int:
	return table.schema.field("vector").type.list_size


def table_dimension() -> int | None:
	"""Vector width of the existing table, or None if the table doesn't exist."""
	db = _connect()
	if TABLE_NAME not in db.list_tables().tables:
		return None
	return _vector_dim(db.open_table(TABLE_NAME))


def ensure_table_for_dimension(dimension: int):
	"""Open the chunks table for the given vector width, creating it if missing.

	An existing table with a different width is an error — the embedding model
	changed and the store must be rebuilt, not silently mixed.
	"""
	if not isinstance(dimension, int) or dimension < 1:
		raise ValueError(f"Invalid embedding dimension: {dimension!r}")

	db = _connect()
	if TABLE_NAME in db.list_tables().tables:
		table = db.open_table(TABLE_NAME)
		existing = _vector_dim(table)
		if existing != dimension:
			frappe.throw(
				_(
					"Knowledge store has dimension {0} but {1} was requested. Rebuild the knowledge store."
				).format(existing, dimension),
				title=_("Embedding Dimension Mismatch"),
			)
		return table

	schema = pa.schema(
		[
			pa.field("id", pa.int64()),
			pa.field("kb", pa.string()),
			pa.field("source", pa.string()),
			pa.field(FTS_FIELD, pa.string()),
			pa.field("vector", pa.list_(pa.float32(), dimension)),
		]
	)
	return db.create_table(TABLE_NAME, schema=schema, exist_ok=True)


def add(rows: list[dict[str, Any]]) -> None:
	"""Insert rows of {id, kb, source, content, vector}. The table must already exist."""
	if not rows:
		return
	table = _open_table()
	table.add(rows)
	_ensure_fts_index(table)


def delete(*, kb: str | None = None, source: str | None = None, ids: list[int] | None = None) -> None:
	"""Delete rows matching ALL given criteria. At least one criterion is required."""
	if kb is None and source is None and ids is None:
		raise ValueError("delete() requires at least one of kb, source, ids")
	if not table_exists():
		return

	conditions = []
	if kb is not None:
		conditions.append(f"kb = {_quote(kb)}")
	if source is not None:
		conditions.append(f"source = {_quote(source)}")
	if ids:
		conditions.append(f"id IN ({', '.join(str(int(i)) for i in ids)})")
	if not conditions:
		return
	_open_table().delete(" AND ".join(conditions))


def search(
	vector: list[float],
	*,
	text: str | None = None,
	kbs: list[str] | None = None,
	limit: int = 5,
) -> list[dict[str, Any]]:
	"""Nearest-neighbour search, optionally scoped to knowledge bases.

	With `text`, runs hybrid search (vector + full-text, rank-fused). Returns
	[{id, kb, source, score}] with higher score = better match.
	"""
	if not table_exists():
		return []
	table = _open_table()
	if table.count_rows() == 0:
		return []

	limit = max(1, min(int(limit), MAX_SEARCH_LIMIT))
	vector = [float(v) for v in vector]

	if text:
		_ensure_fts_index(table)
		query = table.search(query_type="hybrid", vector_column_name="vector").vector(vector).text(text)
	else:
		query = table.search(vector, vector_column_name="vector")
	query = query.distance_type("cosine")

	if kbs:
		query = query.where(f"kb IN ({', '.join(_quote(k) for k in kbs)})", prefilter=True)

	return [
		{
			"id": row["id"],
			"kb": row["kb"],
			"source": row["source"],
			"score": row["_relevance_score"] if text else 1.0 - row["_distance"],
		}
		for row in query.limit(limit).to_list()
	]


def drop_table() -> None:
	db = _connect()
	if TABLE_NAME in db.list_tables().tables:
		db.drop_table(TABLE_NAME)


def _open_table():
	db = _connect()
	if TABLE_NAME not in db.list_tables().tables:
		frappe.throw(
			_("Knowledge store is not initialized. Configure Flow Knowledge Settings and ingest a source."),
			title=_("Knowledge Store Not Ready"),
		)
	return db.open_table(TABLE_NAME)


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
