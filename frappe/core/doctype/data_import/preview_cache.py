# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Redis cache for Data Import preview payloads.

Large CSV/XLSX files are expensive to re-parse on every Preview step load.
Cache keyed by file content + delimiter settings + column map + value mappings
(+ skipped rows + tree parent overrides) so mapping edits, remaps, or tree moves
never return stale warnings/nodes.
Google Sheets previews are never cached — sheet data can change without a URL change.
"""

from __future__ import annotations

import hashlib

import frappe
from frappe.utils import cstr

PREVIEW_CACHE_PREFIX = "data_import_preview"
PREVIEW_CACHE_TTL = 60 * 60  # 1 hour


def _mapping_fingerprint(doc) -> str:
	"""Stable fingerprint of saved value mappings (order-independent)."""
	rows = sorted(
		(
			cstr(row.fieldname),
			cstr(row.parent_field),
			cstr(row.source_value),
			cstr(row.target_value).strip(),
			cstr(getattr(row, "column", None)),
		)
		for row in (doc.get("value_mappings") or [])
	)
	return repr(rows)


def _skipped_rows_fingerprint(doc) -> str:
	"""Sorted skipped sheet row numbers — affects which warnings stay actionable."""
	rows = sorted({int(row.row_number) for row in (doc.get("skipped_rows") or []) if row.row_number})
	return repr(rows)


def _file_fingerprint(file_url: str | None) -> str:
	"""File URL plus content hash so replacing the file at the same URL busts the cache."""
	if not file_url:
		return ""

	meta = frappe.db.get_value(
		"File",
		{"file_url": file_url},
		["content_hash", "modified", "file_size"],
		as_dict=True,
		order_by="modified desc",
	)
	if not meta:
		return cstr(file_url)

	return "|".join(
		[
			cstr(file_url),
			cstr(meta.content_hash),
			cstr(meta.modified),
			cstr(meta.file_size),
		]
	)


def get_preview_cache_key(doc) -> str:
	"""Build a site-scoped Redis key for this Data Import preview fingerprint."""
	parts = [
		cstr(doc.name),
		cstr(doc.reference_doctype),
		cstr(doc.import_type),
		_file_fingerprint(doc.import_file),
		cstr(doc.google_sheets_url),
		cstr(doc.use_csv_sniffer),
		cstr(doc.custom_delimiters),
		cstr(doc.delimiter_options),
		cstr(doc.template_options),
		# Tree move / group edits change preview nodes — must bust the cached payload.
		cstr(doc.tree_parent_overrides),
		_mapping_fingerprint(doc),
		_skipped_rows_fingerprint(doc),
	]
	digest = hashlib.md5("|".join(parts).encode(), usedforsecurity=False).hexdigest()
	return f"{PREVIEW_CACHE_PREFIX}:{doc.name}:{digest}"


def should_cache_preview(doc) -> bool:
	"""Skip cache for Google Sheets — remote content is not bound to a stable file hash."""
	return bool(doc.import_file) and not doc.google_sheets_url


def get_cached_preview(doc):
	"""Return cached preview dict, or None on miss / when caching is disabled."""
	if not should_cache_preview(doc) or not doc.name:
		return None
	return frappe.cache.get_value(get_preview_cache_key(doc))


def set_cached_preview(doc, preview) -> None:
	"""Store preview payload for subsequent Preview step loads."""
	if not should_cache_preview(doc) or not doc.name or preview is None:
		return
	frappe.cache.set_value(get_preview_cache_key(doc), preview, expires_in_sec=PREVIEW_CACHE_TTL)


def clear_preview_cache(data_import_name: str | None) -> None:
	"""Drop all cached previews for a Data Import (any fingerprint)."""
	if not data_import_name:
		return
	frappe.cache.delete_keys(f"{PREVIEW_CACHE_PREFIX}:{data_import_name}:")
