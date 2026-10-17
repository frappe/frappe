# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""Garbage collection for Storage v2.

Deleting a File row never touches bytes synchronously; this daily job
does. A blob is garbage when no Link field pointing to File Blob references
it and it is older than ``MIN_AGE_HOURS``. ``revive_blob`` bumps
``modified`` on a blob being reused, so GC skips it until the new link
commits. Stale upload sessions are swept through
``frappe.storage.upload.expire_stale_upload_sessions``.
"""

from pypika.queries import QueryBuilder, Table
from pypika.terms import Criterion, ExistsCriterion

import frappe
import frappe.storage
from frappe.model.rename_doc import get_link_fields
from frappe.storage.upload import expire_stale_upload_sessions
from frappe.utils import add_to_date, get_datetime, now_datetime

BATCH_SIZE = 500
MIN_AGE_HOURS = 24


def collect_garbage(batch_size: int = BATCH_SIZE) -> dict:
	"""Delete unreferenced File Blob rows older than 24h, and their bytes.

	Batched and defensive: one bad blob is logged and skipped, never
	aborting the sweep. Runs whether or not the ``storage_v2`` flag is on:
	blobs created while the flag was on must still be collected after it
	is turned off. Returns ``{"blobs_deleted": int, "bytes_delete_errors":
	int, "upload_sessions_expired": int}``."""
	stats = {"blobs_deleted": 0, "bytes_delete_errors": 0, "upload_sessions_expired": 0}
	if not frappe.db.table_exists("File Blob"):
		return stats

	logger = frappe.logger("storage")
	cutoff = add_to_date(now_datetime(), hours=-MIN_AGE_HOURS)

	try:
		columns = blob_reference_columns()
		_warn_unindexed_reference_columns(columns, logger)
		orphans = get_orphan_blobs(cutoff, batch_size, columns=columns)
	except Exception:
		# An incomplete set of references must fail closed. Upload expiry is
		# independent and remains useful even when blob collection cannot run.
		logger.error("storage gc: could not inspect all blob references; deleting no blobs", exc_info=True)
		stats["upload_sessions_expired"] = expire_upload_sessions(logger)
		return stats

	while True:
		deleted = 0
		for blob in orphans:
			if delete_blob(blob, cutoff, logger, stats, columns=columns):
				deleted += 1
		stats["blobs_deleted"] += deleted
		if not frappe.flags.in_test:
			# release the row locks taken by delete_blob's re-check
			frappe.db.commit()  # nosemgrep
		if deleted == 0 or len(orphans) < batch_size:
			break
		orphans = get_orphan_blobs(cutoff, batch_size, columns=columns)

	stats["upload_sessions_expired"] = expire_upload_sessions(logger)

	if stats["blobs_deleted"] or stats["upload_sessions_expired"]:
		logger.info(
			"storage gc: deleted {0} blobs, expired {1} upload sessions".format(
				stats["blobs_deleted"], stats["upload_sessions_expired"]
			)
		)
	return stats


def blob_reference_columns() -> list[dict]:
	"""Return every persisted Link column pointing to File Blob."""
	columns = []
	seen = set()
	for field in get_link_fields("File Blob"):
		key = (field["parent"], field["fieldname"])
		if key in seen:
			continue
		seen.add(key)
		columns.append({"doctype": key[0], "fieldname": key[1], "issingle": int(field.get("issingle") or 0)})
	return columns


def orphan_criterion(blob: Table, columns: list[dict]) -> Criterion:
	"""Return one NOT EXISTS probe on ``blob`` per File Blob Link column."""
	return Criterion.all(ExistsCriterion(reference_query(blob, column)).negate() for column in columns)


def reference_query(blob: Table, column: dict) -> QueryBuilder:
	"""Select the rows of one Link column that reference ``blob``."""
	if column["issingle"]:
		ref = frappe.qb.DocType("Singles").as_("ref")
		return (
			frappe.qb.from_(ref)
			.select(1)
			.where(ref.doctype == column["doctype"])
			.where(ref["field"] == column["fieldname"])
			.where(ref.value == blob.name)
		)
	ref = frappe.qb.DocType(column["doctype"]).as_("ref")
	return frappe.qb.from_(ref).select(1).where(ref[column["fieldname"]] == blob.name)


def _warn_unindexed_reference_columns(columns: list[dict], logger) -> None:
	for column in columns:
		if column["issingle"]:
			continue
		table = f"tab{column['doctype']}"
		indexed = frappe.db.get_column_index(table, column["fieldname"], unique=False)
		if not indexed:
			indexed = frappe.db.get_column_index(table, column["fieldname"], unique=True)
		if not indexed:
			logger.warning(
				"storage gc: unindexed File Blob reference {0}.{1}".format(
					column["doctype"], column["fieldname"]
				)
			)


def get_orphan_blobs(cutoff, limit: int, *, columns: list[dict] | None = None) -> list[dict]:
	"""Blobs no discovered Link column references, untouched since ``cutoff``."""
	columns = blob_reference_columns() if columns is None else columns
	blob = frappe.qb.DocType("File Blob").as_("blob")
	return (
		frappe.qb.from_(blob)
		.select(blob.name, blob.key, blob.driver, blob.is_private)
		.where(blob.modified < cutoff)
		.where(orphan_criterion(blob, columns))
		.limit(limit)
		.run(as_dict=True)
	)


def delete_blob(blob, cutoff, logger, stats: dict, *, columns: list[dict] | None = None) -> bool:
	"""Delete one blob's bytes, then its row. Return True when the row is gone.

	Re-verifies the orphan status under a row lock first, and re-reads
	``key``/``driver``/``is_private`` under that same lock rather than trusting
	``blob``'s scan-time values: a concurrent ``relocate_blobs()`` run can move
	the blob to a new location between ``get_orphan_blobs`` and this call.
	Deleting bytes at the stale location would leave the blob's *current*
	bytes behind with no row left to ever find them, once this deletes the
	row. ``revive_blob`` (``put_blob`` dedup, ``File.revive_linked_blob``) can
	revive a selected orphan concurrently (it locks the row and bumps
	``modified``), and a new File row may have appeared since
	``get_orphan_blobs`` ran. Drivers treat a missing object as
	a no-op delete. On a driver error the row is kept so the next run
	retries."""
	current = is_still_orphan(blob.name, cutoff, columns=columns)
	if not current:
		return False

	try:
		driver = frappe.storage.get_driver(current.driver)
		driver.delete(current.key, is_private=bool(current.is_private))
	except Exception:
		stats["bytes_delete_errors"] += 1
		logger.warning(
			f"storage gc: could not delete bytes of blob {blob.name} (key {current.key})", exc_info=True
		)
		return False

	try:
		frappe.delete_doc("File Blob", blob.name, force=1, ignore_permissions=True, ignore_missing=True)
		logger.info(f"storage gc: deleted blob {blob.name} (key {current.key}, driver {current.driver})")
		return True
	except Exception:
		logger.warning(f"storage gc: could not delete File Blob row {blob.name}", exc_info=True)
		return False


def is_still_orphan(blob_name: str, cutoff, *, columns: list[dict] | None = None):
	"""Lock the blob row; return its current fields if still unreferenced and stale.

	Returns ``None`` when the row is gone, was touched since ``cutoff``, or is
	referenced again. Otherwise returns a ``_dict`` with the row's current
	``key``, ``driver``, and ``is_private``, read under the same lock, so a
	caller always deletes bytes at the blob's up-to-date location even when a
	concurrent ``relocate_blobs()`` run moved it after the candidate scan."""
	row = frappe.db.get_value(
		"File Blob", blob_name, ["modified", "key", "driver", "is_private"], for_update=True, as_dict=True
	)
	if not row or get_datetime(row.modified) >= get_datetime(cutoff):
		return None
	columns = blob_reference_columns() if columns is None else columns
	blob = frappe.qb.DocType("File Blob").as_("blob")
	still_orphan = (
		frappe.qb.from_(blob)
		.select(blob.name)
		.where(blob.name == blob_name)
		.where(orphan_criterion(blob, columns))
		.run()
	)
	return row if still_orphan else None


def expire_upload_sessions(logger) -> int:
	"""Sweep stale upload sessions. A failed sweep is logged, not raised."""
	try:
		return expire_stale_upload_sessions() or 0
	except Exception:
		logger.warning("storage gc: expire_stale_upload_sessions failed", exc_info=True)
		return 0
