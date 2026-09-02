# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""Backfill File Blob rows for legacy File rows.

Groups legacy rows (no blob, non-folder, non-remote, local ``file_url``)
by ``(path, is_private)`` and creates one Ready ``local`` blob per
group. Bytes are NOT moved: the blob key points at the legacy path,
and ``file_url`` stays unchanged. Rows link to the blob through plain
``db.set_value`` (no doc events). Missing or unreadable disk files are
logged and skipped. Idempotent: linked rows are not refetched and
existing blobs are reused through the ``(checksum, is_private, driver)``
dedup lookup.

Legacy keys: ``LocalDriver`` resolves keys relative to
``{public,private}/files/blobs/``, so a legacy path under the files root
is stored with a ``../`` prefix, e.g. ``../logo.png`` for
``public/files/logo.png``. The driver confines resolved paths to the
files root, so these keys stay inside the site.
"""

import os

import frappe
from frappe.storage.blob import sha256_of, sniff_mime
from frappe.utils import cint, get_files_path

PUBLIC_PREFIX = "/files/"
PRIVATE_PREFIX = "/private/files/"


def run(batch_size: int = 500, filters: dict | None = None) -> dict:
	"""Backfill blobs for legacy File rows. Safe to re-run.

	``filters`` narrows the File query (tests use it to stay off real
	site rows). Returns ``{"linked": int, "blobs_created": int,
	"skipped": [{"name", "file_url", "reason"}]}``."""
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


def get_legacy_rows(limit: int, after_name: str, filters: dict | None) -> list[dict]:
	"""Next batch of legacy rows, keyset-paginated by name."""
	query_filters = {
		"blob": ("is", "not set"),
		"is_folder": 0,
		"name": (">", after_name),
	}
	query_filters.update(filters or {})
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

	# Cache by resolved path, never by the legacy content_hash: that hash
	# is MD5 and may be stale, so two rows can share it while their bytes
	# differ. Rows that share a path share bytes by definition. Distinct
	# paths are hashed and still collapse onto one blob through the
	# SHA-256 dedup lookup in find_or_create_blob.
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
	"""Reuse a blob by checksum or create one keyed at the legacy path."""
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

	existing = frappe.db.get_value(
		"File Blob",
		{"checksum": checksum, "is_private": cint(is_private), "driver": "local"},
	)
	if existing:
		return existing

	blob = frappe.new_doc("File Blob")
	blob.update(
		{
			"key": f"../{rel_path}",
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
