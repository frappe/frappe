# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Site-scoped SQLite vector store.

MariaDB (Flow Knowledge Chunk) is the source of truth for chunk text and metadata.
This store holds only what search needs: the vector, scoping columns, and a copy
of the content for the full-text index. Row `id` is the chunk's autoincrement name,
so every hit maps back to its MariaDB row. The whole store is disposable — it can
be rebuilt from MariaDB at any time.

The same file also holds chat attachment chunks and agent memories. Each table has a
full-text index kept in sync by triggers.
"""

from __future__ import annotations

import atexit
import os
import re
import shutil
import sqlite3
import tempfile
from collections import defaultdict
from contextlib import contextmanager
from typing import Any

import sqlite_vec

import frappe
from frappe import _

DB_FILE = "flow_search.db"
TABLE_NAME = "chunks"
MAX_SEARCH_LIMIT = 100
# hybrid score: sum of 1 / (RRF_K + rank)
RRF_K = 60
# common words left out of keyword queries
STOP_WORDS = frozenset(
	"a an and are as at be but by for if in into is it no not of on or such that the their then "
	"there these they this to was will with".split()
)


def db_path() -> str:
	if frappe.flags.in_test:
		return os.path.join(_test_db_path(), DB_FILE)
	# outside private/files, so no File row can expose it
	return frappe.get_site_path("private", DB_FILE)


_test_db: str | None = None


def _test_db_path() -> str:
	"""A throwaway store for the test run, removed when the process exits."""
	global _test_db
	if _test_db is None:
		_test_db = tempfile.mkdtemp(prefix="flow-search-")
		atexit.register(shutil.rmtree, _test_db, ignore_errors=True)
	return _test_db


@contextmanager
def _connect(write: bool = False):
	"""Open the store. With `write`, the block is one transaction."""
	db = sqlite3.connect(db_path(), timeout=30)
	try:
		db.enable_load_extension(True)
		sqlite_vec.load(db)
		db.enable_load_extension(False)
		with db:
			if write:
				db.execute("begin immediate")
			yield db
	finally:
		db.close()


def table_exists() -> bool:
	with _connect() as db:
		return _shape(db, TABLE_NAME) is not None


def table_dimension() -> int | None:
	"""Vector width of the existing table, or None if the table doesn't exist."""
	with _connect() as db:
		shape = _shape(db, TABLE_NAME)
	return int(shape) if shape else None


def ensure_table_for_dimension(dimension: int) -> None:
	"""Create the chunks table for the given vector width if it is missing.

	An existing table with a different width is an error — the embedding model
	changed and the store must be rebuilt, not silently mixed.
	"""
	if not isinstance(dimension, int) or dimension < 1:
		raise ValueError(f"Invalid embedding dimension: {dimension!r}")

	with _connect(write=True) as db:
		existing = _shape(db, TABLE_NAME)
		if existing is None:
			_create_table(db, TABLE_NAME, "id integer primary key, kb text, source text", dimension)
			db.execute(f"create index {TABLE_NAME}_kb on {TABLE_NAME}(kb)")
			db.execute(f"create index {TABLE_NAME}_source on {TABLE_NAME}(source)")
		elif int(existing) != dimension:
			frappe.throw(
				_(
					"Knowledge store has dimension {0} but {1} was requested. Rebuild the knowledge store."
				).format(existing, dimension),
				title=_("Embedding Dimension Mismatch"),
			)


def add(rows: list[dict[str, Any]]) -> None:
	"""Insert rows of {id, kb, source, content, vector}. The table must already exist."""
	if not rows:
		return
	with _connect(write=True) as db:
		if _shape(db, TABLE_NAME) is None:
			frappe.throw(
				_(
					"Knowledge store is not initialized. Configure Flow Knowledge Settings and ingest a source."
				),
				title=_("Knowledge Store Not Ready"),
			)
		# replace rows whose id is already here
		db.executemany(f"delete from {TABLE_NAME} where id = ?", [(row["id"],) for row in rows])
		db.executemany(
			f"insert into {TABLE_NAME}(id, kb, source, content, vector) values (?, ?, ?, ?, ?)",
			[
				(
					row["id"],
					row["kb"],
					row["source"],
					row["content"],
					_vector_bytes(row["vector"]),
				)
				for row in rows
			],
		)


def delete(*, kb: str | None = None, source: str | None = None, ids: list[int] | None = None) -> None:
	"""Delete rows matching ALL given criteria. At least one criterion is required."""
	if kb is None and source is None and ids is None:
		raise ValueError("delete() requires at least one of kb, source, ids")

	conditions, values = [], []
	if kb is not None:
		conditions.append("kb = ?")
		values.append(kb)
	if source is not None:
		conditions.append("source = ?")
		values.append(source)
	if ids:
		conditions.append("id = ?")
	if not conditions:
		return
	with _connect(write=True) as db:
		if _shape(db, TABLE_NAME) is not None:
			# one delete per id, so any number of ids works
			db.executemany(
				f"delete from {TABLE_NAME} where {' and '.join(conditions)}",
				[(*values, int(i)) for i in ids] if ids else [values],
			)


def rename_kb(old: str, new: str) -> None:
	"""Move a renamed knowledge base's chunks to its new name."""
	with _connect(write=True) as db:
		if _shape(db, TABLE_NAME) is not None:
			db.execute(f"update {TABLE_NAME} set kb = ? where kb = ?", (new, old))


def move_source(source: str, kb: str) -> None:
	"""Move a source's chunks to another knowledge base."""
	with _connect(write=True) as db:
		if _shape(db, TABLE_NAME) is not None:
			db.execute(f"update {TABLE_NAME} set kb = ? where source = ?", (kb, source))


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
	limit = max(1, min(int(limit), MAX_SEARCH_LIMIT))
	where, values = "1", []
	if kbs:
		where, values = f"kb in ({_placeholders(kbs)})", list(kbs)

	with _connect() as db:
		if _shape(db, TABLE_NAME) is None:
			return []
		hits = _search(db, TABLE_NAME, "id, kb, source", where, values, vector, text, limit)
	return [{"id": id, "kb": kb, "source": source, "score": score} for id, kb, source, score in hits]


def drop_table() -> None:
	with _connect(write=True) as db:
		_drop_table(db, TABLE_NAME)


# --- shared helpers ------------------------------------------------------------


def _search(
	db, table: str, columns: str, where: str, values: list, vector: list[float], text: str | None, limit: int
) -> list[tuple]:
	"""Best rows matching `where`, as (*columns, score). With `text`, vector and keyword
	ranks are merged."""
	nearest = db.execute(
		f"select rowid, vec_distance_cosine(vector, ?) as distance from {table} "
		# a zero vector has no distance
		f"where ({where}) and distance is not null order by distance limit ?",
		[_vector_bytes(vector), *values, limit],
	).fetchall()
	if text:
		scores: dict[int, float] = defaultdict(float)
		for ranked_rowids in (
			[rowid for rowid, _ in nearest],
			_keyword_search(db, table, where, values, text, limit),
		):
			for rank, rowid in enumerate(ranked_rowids, 1):
				scores[rowid] += 1 / (RRF_K + rank)
	else:
		scores = {rowid: 1.0 - distance for rowid, distance in nearest}

	best = sorted(scores, key=scores.get, reverse=True)[:limit]
	rows = {
		row[0]: row[1:]
		for row in db.execute(
			# filtered again: a deleted row's id can be reused by another scope
			f"select rowid, {columns} from {table} where rowid in ({_placeholders(best)}) and ({where})",
			[*best, *values],
		)
	}
	# skip rows deleted meanwhile
	return [(*rows[rowid], scores[rowid]) for rowid in best if rowid in rows]


def _keyword_search(db, table: str, where: str, values: list, text: str, limit: int) -> list[int]:
	"""Rowids of the best keyword matches for `text`."""
	# FTS5 rejects raw text, so each word is quoted
	words = dict.fromkeys(re.findall(r"[^\W_]+", text.lower()))
	match = " OR ".join(f'"{word}"' for word in words if word not in STOP_WORDS)
	if not match:
		return []
	fts = f"{table}_fts"
	query = (
		f"select {table}.rowid from {fts} join {table} on {table}.rowid = {fts}.rowid "
		f"where {fts} match ? and ({where}) order by {fts}.rank limit ?"
	)
	return [row[0] for row in db.execute(query, [match, *values, limit])]


def _create_table(db, table: str, columns: str, dimension: int, shape: str | None = None) -> None:
	"""Create `table` with a full-text index. `dimension` 0 means no vectors."""
	size_check = f" check(length(vector) = {int(dimension) * 4})" if dimension else ""
	fts = f"{table}_fts"
	add_to_fts = f"insert into {fts}(rowid, content) values (new.rowid, new.content);"
	remove_from_fts = f"insert into {fts}({fts}, rowid, content) values ('delete', old.rowid, old.content);"
	for statement in (
		"create table if not exists meta(name text primary key, shape text)",
		# vector last, so other columns read without loading it
		f"create table {table}({columns}, content text, vector blob{size_check})",
		f"create virtual table {fts} using fts5("
		f"content, content='{table}', tokenize='porter unicode61 remove_diacritics 2')",
		f"create trigger {table}_added after insert on {table} begin {add_to_fts} end",
		f"create trigger {table}_deleted after delete on {table} begin {remove_from_fts} end",
		f"create trigger {table}_edited after update of content on {table} begin {remove_from_fts} {add_to_fts} end",
	):
		db.execute(statement)
	db.execute("insert into meta values (?, ?)", (table, shape or str(dimension)))


def _drop_table(db, table: str) -> None:
	if _shape(db, table) is None:
		return
	db.execute(f"drop table {table}_fts")
	db.execute(f"drop table {table}")  # its triggers and indexes go with it
	db.execute("delete from meta where name = ?", (table,))


def _shape(db, table: str) -> str | None:
	"""The table's vector width or marker, None if it doesn't exist."""
	if not db.execute("select 1 from sqlite_master where name = 'meta'").fetchone():
		return None
	row = db.execute("select shape from meta where name = ?", (table,)).fetchone()
	return row[0] if row else None


def _vector_bytes(vector: list[float]) -> bytes:
	"""Vector as a float32 blob."""
	return sqlite_vec.serialize_float32(vector)


def _placeholders(values) -> str:
	return ", ".join("?" * len(values))
