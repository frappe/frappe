# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Ingestion pipeline: turn a knowledge source into MariaDB chunks + LanceDB rows.

MariaDB (Flow Knowledge Chunk) is the source of truth; the LanceDB store is a
derived index keyed by chunk name.

- Text / File / URL are single documents: each run rebuilds them from scratch.
- DocType sources are incremental. A watermark (last_synced_at) bounds each run
  to rows modified since the last sweep; a per-row content hash skips re-embedding
  unchanged rows; deletions and filter-exits are pulled from Deleted Document and
  the changed set, so nothing is enqueued per row.
"""

from __future__ import annotations

import hashlib

import frappe
from frappe.utils import cint, now_datetime

CHUNK_DOCTYPE = "Flow Knowledge Chunk"
BATCH = 500


def enqueue_ingestion(source: str, rebuild: bool = False) -> None:
	frappe.enqueue(
		"flow.knowledge.ingest.ingest_source",
		queue="long",
		enqueue_after_commit=True,
		source=source,
		rebuild=rebuild,
	)


def sync_due_sources() -> None:
	"""Daily scheduler: enqueue an incremental sweep for every auto-sync DocType source."""
	sources = frappe.get_all(
		"Flow Knowledge Source",
		filters={"source_type": "DocType", "auto_sync": 1},
		pluck="name",
	)
	for source in sources:
		enqueue_ingestion(source)


def enqueue_reconciliation(source: str) -> None:
	frappe.enqueue(
		"flow.knowledge.ingest.reconcile_source",
		queue="long",
		enqueue_after_commit=True,
		source=source,
	)


def ingest_source(source: str, rebuild: bool = False) -> None:
	"""Worker: bring a source's chunks in both stores up to date.

	rebuild forces a full re-chunk of a DocType source (purge + reset watermark) so
	new chunk settings apply to rows whose content is otherwise unchanged. Single-doc
	sources rebuild on every run regardless."""
	doc = frappe.get_doc("Flow Knowledge Source", source)
	doc.db_set("status", "Processing", update_modified=False)
	frappe.db.commit()

	try:
		settings = frappe.get_cached_doc("Flow Knowledge Settings")
		if doc.source_type == "DocType":
			if rebuild:
				purge_source(doc.name)
				doc.db_set("last_synced_at", None, update_modified=False)
			_sync_doctype(doc, settings)
		else:
			_rebuild_single(doc, settings)
	except Exception:
		frappe.db.rollback()
		_mark_failed(source)
		raise

	count = frappe.db.count(CHUNK_DOCTYPE, {"source": doc.name})
	doc.db_set(
		{"status": "Completed", "chunk_count": count, "error_log": None},
		update_modified=False,
	)
	frappe.db.commit()


def purge_source(source: str) -> None:
	"""Remove a source's chunks from both stores. Safe to call repeatedly."""
	from flow.knowledge import store

	store.delete(source=source)
	frappe.db.delete(CHUNK_DOCTYPE, {"source": source})


# --- single-document sources (Text / File / URL) -----------------------------


def _rebuild_single(doc, settings) -> None:
	"""Re-extract, chunk, embed, and replace all chunks for a single-doc source."""
	from flow.knowledge import store
	from flow.knowledge.chunker import chunk_text
	from flow.knowledge.embedder import embed_texts
	from flow.knowledge.extract import extract

	size, overlap = _chunk_params(doc, settings)
	pieces = []
	for extracted in extract(doc):
		pieces.extend(chunk_text(extracted.text, chunk_size=size, overlap=overlap))

	purge_source(doc.name)
	if not pieces:
		return

	vectors = embed_texts(pieces)
	store.ensure_table_for_dimension(cint(settings.embedding_dimension))

	rows = []
	for index, (piece, vector) in enumerate(zip(pieces, vectors, strict=True)):
		chunk_doc = frappe.get_doc(
			{
				"doctype": CHUNK_DOCTYPE,
				"knowledge_base": doc.knowledge_base,
				"source": doc.name,
				"chunk_index": index,
				"content": piece,
			}
		).insert(ignore_permissions=True)
		rows.append(
			{
				"id": int(chunk_doc.name),
				"kb": doc.knowledge_base,
				"source": doc.name,
				"content": piece,
				"vector": vector,
			}
		)

	store.add(rows)


# --- DocType sources (incremental) -------------------------------------------


def _sync_doctype(doc, settings) -> None:
	"""Watermark sweep: upsert changed rows (hash-gated), then remove rows that
	were deleted or fell out of the filter since the last sweep."""
	from flow.knowledge.extract import _parse_filters, resolve_content_fields

	ref = doc.reference_doctype
	meta = frappe.get_meta(ref)
	fields = resolve_content_fields(meta, doc.content_fields)
	user_filters = _parse_filters(doc.filters)
	watermark = doc.last_synced_at
	sweep_start = now_datetime()
	first_run = not watermark

	delta = {} if first_run else {"modified": [">", watermark]}
	matched_refs: set[str] = set()
	start = 0
	while True:
		page = frappe.get_all(
			ref,
			filters={**user_filters, **delta},
			fields=["name", *fields],
			order_by="modified asc, name asc",
			limit_start=start,
			limit_page_length=BATCH,
		)
		if not page:
			break
		_upsert_page(doc, settings, meta, fields, page, matched_refs, track_exits=not first_run)
		start += BATCH
		if len(page) < BATCH:
			break

	if not first_run:
		_remove_stale(doc, ref, watermark, matched_refs)

	doc.db_set("last_synced_at", sweep_start, update_modified=False)


def _upsert_page(doc, settings, meta, fields, page, matched_refs, *, track_exits) -> None:
	from flow.knowledge.extract import _row_to_text

	to_embed = []  # (reference_name, content_hash, [pieces])
	stale = []  # reference_names whose chunks must go (content changed or now empty)
	for row in page:
		name = row["name"]
		if track_exits:
			matched_refs.add(name)
		existing = _existing_chunk_state(doc.name, name)
		text = _row_to_text(row, fields, meta)
		if not text:
			if existing["ids"]:
				stale.append(name)
			continue
		new_hash = _content_hash(text)
		if existing["hash"] == new_hash:
			continue
		if existing["ids"]:
			stale.append(name)
		pieces = _chunk(text, doc, settings)
		if pieces:
			to_embed.append((name, new_hash, pieces))

	if stale:
		_purge_refs(doc.name, stale)
	if to_embed:
		_embed_and_insert(doc, settings, to_embed)


def _embed_and_insert(doc, settings, to_embed) -> None:
	from flow.knowledge import store
	from flow.knowledge.embedder import embed_texts

	all_pieces = []
	for _, _, pieces in to_embed:
		all_pieces.extend(pieces)
	vectors = embed_texts(all_pieces)
	store.ensure_table_for_dimension(cint(settings.embedding_dimension))

	rows = []
	cursor = 0
	for reference_name, content_hash, pieces in to_embed:
		for index, piece in enumerate(pieces):
			vector = vectors[cursor]
			cursor += 1
			chunk_doc = frappe.get_doc(
				{
					"doctype": CHUNK_DOCTYPE,
					"knowledge_base": doc.knowledge_base,
					"source": doc.name,
					"chunk_index": index,
					"content": piece,
					"content_hash": content_hash,
					"reference_doctype": doc.reference_doctype,
					"reference_name": reference_name,
				}
			).insert(ignore_permissions=True)
			rows.append(
				{
					"id": int(chunk_doc.name),
					"kb": doc.knowledge_base,
					"source": doc.name,
					"content": piece,
					"vector": vector,
				}
			)

	store.add(rows)


def _remove_stale(doc, ref, watermark, matched_refs) -> None:
	touched = {
		row["name"] for row in frappe.get_all(ref, filters={"modified": [">", watermark]}, fields=["name"])
	}
	exits = touched - matched_refs
	deleted = set(
		frappe.get_all(
			"Deleted Document",
			filters={"deleted_doctype": ref, "creation": [">", watermark]},
			pluck="deleted_name",
		)
	)
	to_remove = exits | deleted
	if to_remove:
		_purge_refs(doc.name, list(to_remove))


def _existing_chunk_state(source, reference_name) -> dict:
	rows = frappe.get_all(
		CHUNK_DOCTYPE,
		filters={"source": source, "reference_name": reference_name},
		fields=["name", "content_hash"],
	)
	return {
		"ids": [int(r["name"]) for r in rows],
		"hash": rows[0]["content_hash"] if rows else None,
	}


def _purge_refs(source, reference_names) -> None:
	from flow.knowledge import store

	for start in range(0, len(reference_names), BATCH):
		criterion = {"source": source, "reference_name": ["in", reference_names[start : start + BATCH]]}
		ids = [int(name) for name in frappe.get_all(CHUNK_DOCTYPE, filters=criterion, pluck="name")]
		if ids:
			store.delete(ids=ids)
			frappe.db.delete(CHUNK_DOCTYPE, criterion)


# --- reconciliation (manual, full scan) --------------------------------------


def reconcile_source(source: str) -> None:
	"""Purge chunks whose reference row no longer exists. Full scan — cleans up after
	hard deletes that left no tombstone (delete_permanently, raw SQL). Expensive, so it
	is triggered manually, never on the sweep."""
	doc = frappe.get_doc("Flow Knowledge Source", source)
	if doc.source_type != "DocType":
		return

	indexed = set(
		frappe.get_all(CHUNK_DOCTYPE, filters={"source": source}, pluck="reference_name", distinct=True)
	)
	indexed.discard(None)
	if not indexed:
		return

	orphaned = list(indexed - _existing_names(doc.reference_doctype, indexed))
	if orphaned:
		_purge_refs(source, orphaned)
		count = frappe.db.count(CHUNK_DOCTYPE, {"source": source})
		doc.db_set("chunk_count", count, update_modified=False)


def _existing_names(doctype: str, names: set[str]) -> set[str]:
	"""Names from `names` that still exist as rows, fetched in bounded batches so a
	huge indexed set never builds one oversized IN clause."""
	found: set[str] = set()
	ordered = list(names)
	for start in range(0, len(ordered), BATCH):
		batch = ordered[start : start + BATCH]
		found.update(frappe.get_all(doctype, filters={"name": ["in", batch]}, pluck="name"))
	return found


def _chunk(text, doc, settings) -> list[str]:
	from flow.knowledge.chunker import chunk_text

	size, overlap = _chunk_params(doc, settings)
	return chunk_text(text, chunk_size=size, overlap=overlap)


def _chunk_params(doc, settings) -> tuple[int, int]:
	"""Per-source chunk size/overlap, each falling back to the global default when 0."""
	size = cint(doc.chunk_size) or cint(settings.chunk_size)
	overlap = cint(doc.chunk_overlap) or cint(settings.chunk_overlap)
	return size, overlap


def _content_hash(text: str) -> str:
	return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _mark_failed(source: str) -> None:
	error = frappe.get_traceback(with_context=True)
	frappe.db.set_value(
		"Flow Knowledge Source",
		source,
		{"status": "Failed", "error_log": error},
		update_modified=False,
	)
	frappe.db.commit()
