# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""Backfill File Blob rows for legacy File rows. See "Backfill and compatibility" in SPEC.md.

One ``local`` blob per disk path, keyed at that path under the files root
(``logo.png`` for ``public/files/logo.png``). Bytes and ``file_url`` stay put."""

import os

import frappe
from frappe.storage.blob import sha256_of, sniff_mime
from frappe.storage.url import PRIVATE_PREFIX, PUBLIC_PREFIX
from frappe.utils import cint, get_files_path


def run(batch_size: int = 500, filters: list | None = None) -> dict:
	"""Backfill blobs for legacy File rows. Safe to re-run. Return counts and skipped rows.

	``filters`` narrows the File query."""
	stats = {"linked": 0, "blobs_created": 0, "skipped": []}
	logger = frappe.logger("storage")
	blob_cache: dict[tuple, str] = {}
	after_name = ""

	while True:
		rows = get_legacy_rows(batch_size, after_name, filters)
		if not rows:
			break
		for row in rows:
			process_row(row, blob_cache, stats, logger)
		after_name = rows[-1].name
		if not frappe.flags.in_test:
			frappe.db.commit()  # batched migration: each page is committed so a rerun resumes  # nosemgrep
		if len(rows) < batch_size:
			break

	logger.info(
		"storage backfill: linked {0} File rows, created {1} blobs, skipped {2}".format(
			stats["linked"], stats["blobs_created"], len(stats["skipped"])
		)
	)
	return stats


def get_legacy_rows(limit: int, after_name: str, filters: list | None) -> list[dict]:
	"""Next batch of legacy rows, keyset-paginated by name."""
	query_filters = [
		["blob", "is", "not set"],
		["is_folder", "=", 0],
		["name", ">", after_name],
		*(filters or []),
	]
	return frappe.get_all(
		"File",
		filters=query_filters,
		or_filters=[
			["file_url", "like", PUBLIC_PREFIX + "%"],
			["file_url", "like", PRIVATE_PREFIX + "%"],
		],
		fields=["name", "file_url", "is_private"],
		order_by="name asc",
		limit=limit,
	)


def process_row(row, blob_cache: dict, stats: dict, logger) -> None:
	located = locate(row.file_url)
	if not located:
		skip(row, "file_url is not a local files path", stats, logger)
		return
	is_private, rel_path = located

	# by path, never by the legacy content_hash: it may be stale. Distinct
	# paths never share a blob, so each disk file has one owner to free it.
	group = (rel_path, is_private)
	blob_name = blob_cache.get(group)
	if not blob_name:
		blob_name = find_or_create_blob(rel_path, is_private, row, stats, logger)
		if not blob_name:
			return
		blob_cache[group] = blob_name

	frappe.db.set_value("File", row.name, "blob", blob_name, update_modified=False)
	stats["linked"] += 1


def locate(file_url: str) -> tuple[bool, str] | None:
	"""Split a legacy file_url into (is_private, path under the files root).

	None when the URL is remote, absolute-escaping, or traverses out."""
	if file_url.startswith(PRIVATE_PREFIX):
		is_private, rel_path = True, file_url[len(PRIVATE_PREFIX) :]
	elif file_url.startswith(PUBLIC_PREFIX):
		is_private, rel_path = False, file_url[len(PUBLIC_PREFIX) :]
	else:
		return None

	rel_path = rel_path.strip("/")
	if not rel_path or os.path.isabs(rel_path) or ".." in rel_path.split("/"):
		return None
	return is_private, rel_path


def find_or_create_blob(rel_path: str, is_private: bool, row, stats: dict, logger) -> str | None:
	"""Reuse the blob keyed at the legacy path or create one there."""
	existing = frappe.db.get_value(
		"File Blob", {"key": rel_path, "is_private": cint(is_private), "driver": "local"}
	)
	if existing:
		return existing

	full_path = get_files_path(rel_path, is_private=is_private)
	try:
		# path comes from locate(), which rejects absolute paths and any '..' segment
		# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
		with open(full_path, "rb") as f:
			checksum = sha256_of(f)
			mime_type = sniff_mime(f)
		file_size = os.path.getsize(full_path)
	except OSError as e:
		skip(row, f"cannot read {full_path}: {e}", stats, logger)
		return None

	blob = frappe.new_doc("File Blob")
	blob.update(
		{
			"key": rel_path,
			"checksum": checksum,
			"file_size": file_size,
			"mime_type": mime_type,
			"driver": "local",
			"is_private": cint(is_private),
			"status": "Ready",
		}
	)
	blob.insert(ignore_permissions=True)
	stats["blobs_created"] += 1
	return blob.name


def skip(row, reason: str, stats: dict, logger) -> None:
	stats["skipped"].append({"name": row.name, "file_url": row.file_url, "reason": reason})
	logger.warning(f"storage backfill: skipped File {row.name} ({row.file_url}): {reason}")
