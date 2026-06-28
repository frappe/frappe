# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Query-time retrieval over the knowledge store.

Embeds the query, runs a KB-scoped search (hybrid or vector-only per the
Flow Knowledge Settings search_type), and hydrates each hit from MariaDB (the
source of truth) for its text and provenance.

Permission model — the knowledge base is the boundary. KBs are admin-curated
(System Manager-only doctypes), bound to agents by admins, and the LLM cannot
widen the scope. Retrieval is therefore not re-checked per chunk against the
running user; the binding is the authorization. The two gates are: scoping is
fail-closed (an empty scope is refused, never widened to the whole store), and
only knowledge bases that currently exist and are enabled are searched, so
disabling a KB is a real off-switch.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

KB_DOCTYPE = "Flow Knowledge Base"
CHUNK_DOCTYPE = "Flow Knowledge Chunk"
DEFAULT_LIMIT = 5


def retrieve_attachments(query: str, *, session: str, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
	"""Best-matching chunks from the files attached to `session`, most relevant first.

	Scoping to `session` is the boundary (enforced upstream by the session-owner check).
	Returns [{content, score}]; empty on a blank query or when nothing is indexed.
	"""
	query = (query or "").strip()
	if not query or not session:
		return []

	from flow.knowledge import attachment_store
	from flow.knowledge.embedder import embed_texts

	search_type = frappe.get_cached_value("Flow Knowledge Settings", "Flow Knowledge Settings", "search_type")
	text = query if search_type != "Vector" else None

	(vector,) = embed_texts([query])
	return attachment_store.search(vector, session=session, text=text, limit=limit)


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

	kbs = _enabled_kbs(kbs)
	if not kbs:
		return []

	from flow.knowledge import store
	from flow.knowledge.embedder import embed_texts

	search_type = frappe.get_cached_value("Flow Knowledge Settings", "Flow Knowledge Settings", "search_type")
	text = query if search_type != "Vector" else None

	(vector,) = embed_texts([query])
	hits = store.search(vector, text=text, kbs=kbs, limit=limit)
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


def _enabled_kbs(kbs: list[str]) -> list[str]:
	"""Keep only knowledge bases that still exist and are enabled. Disabling or
	deleting a KB removes it from every bound agent's reach without re-binding."""
	return frappe.get_all(KB_DOCTYPE, filters={"name": ["in", kbs], "enabled": 1}, pluck="name")


def _hydrate(ids: set[int]) -> dict[int, dict[str, Any]]:
	rows = frappe.get_all(
		CHUNK_DOCTYPE,
		filters={"name": ["in", list(ids)]},
		fields=["name", "content", "source", "reference_doctype", "reference_name"],
	)
	return {int(row["name"]): row for row in rows}
