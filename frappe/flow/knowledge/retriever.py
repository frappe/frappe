# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Query-time retrieval over the knowledge store.

Embeds the query, runs a KB-scoped hybrid search, and hydrates each hit from
MariaDB (the source of truth) for its text and provenance. Scoping is
fail-closed: retrieval without a knowledge base is refused, never widened to
the whole store.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

CHUNK_DOCTYPE = "AI Knowledge Chunk"
DEFAULT_LIMIT = 5


def retrieve(query: str, *, kbs: list[str], limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
	"""Return the best-matching chunks within `kbs`, most relevant first.

	`kbs` must be non-empty — an empty scope is refused, not read as "all".
	"""
	if not kbs:
		frappe.throw(
			_("Knowledge search requires at least one knowledge base."),
			title=_("No Knowledge Base"),
		)
	query = (query or "").strip()
	if not query:
		return []

	from flow.knowledge import store
	from flow.knowledge.embedder import embed_texts

	(vector,) = embed_texts([query])
	hits = store.search(vector, text=query, kbs=kbs, limit=limit)
	if not hits:
		return []

	chunks = _hydrate({int(hit["id"]) for hit in hits})
	results: list[dict[str, Any]] = []
	for hit in hits:
		chunk = chunks.get(int(hit["id"]))
		if chunk is None:
			continue
		results.append(
			{
				"content": chunk["content"],
				"score": hit["score"],
				"source": chunk["source"],
				"reference_doctype": chunk.get("reference_doctype"),
				"reference_name": chunk.get("reference_name"),
			}
		)
	return results


def _hydrate(ids: set[int]) -> dict[int, dict[str, Any]]:
	rows = frappe.get_all(
		CHUNK_DOCTYPE,
		filters={"name": ["in", list(ids)]},
		fields=["name", "content", "source", "reference_doctype", "reference_name"],
	)
	return {int(row["name"]): row for row in rows}
