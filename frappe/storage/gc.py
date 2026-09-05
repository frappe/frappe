# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""Garbage collection for Storage v2.

Deleting a File row never touches bytes synchronously; this daily job
does. A blob is garbage when no Link field pointing to File Blob references
it and it is older than ``MIN_AGE_HOURS``. That covers rolled-back writes
and stale ``Pending`` blobs from aborted uploads. Stale upload sessions are
swept through ``frappe.storage.upload.expire_stale_upload_sessions``.
"""

import frappe
import frappe.storage
from frappe.model.rename_doc import get_link_fields
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
		predicate = orphan_predicate(columns=columns)
		orphans = get_orphan_blobs(cutoff, batch_size, predicate=predicate)
	except Exception:
		# An incomplete set of references must fail closed. Upload expiry is
		# independent and remains useful even when blob collection cannot run.
		logger.error("storage gc: could not inspect all blob references; deleting no blobs", exc_info=True)
		stats["upload_sessions_expired"] = expire_upload_sessions(logger)
		return stats

	while True:
		deleted = 0
		for blob in orphans:
			if delete_blob(blob, cutoff, logger, stats, predicate=predicate):
				deleted += 1
		stats["blobs_deleted"] += deleted
		if not frappe.flags.in_test:
			# release the row locks taken by delete_blob's re-check
			frappe.db.commit()  # nosemgrep
		if deleted == 0 or len(orphans) < batch_size:
			break
		orphans = get_orphan_blobs(cutoff, batch_size, predicate=predicate)

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
		columns.append(
			{"doctype": key[0], "fieldname": key[1], "issingle": int(field.get("issingle") or 0)}
		)
	return columns


def orphan_predicate(blob_alias: str = "b", *, columns: list[dict] | None = None) -> str:
	"""Return one NOT EXISTS probe per discovered File Blob Link column."""
	return _orphan_predicate(
		blob_reference_columns() if columns is None else columns,
		blob_alias=blob_alias,
	)


def _orphan_predicate(columns: list[dict], blob_alias: str = "b") -> str:
	predicates = []
	blob = _quote_identifier(blob_alias)
	for column in columns:
		doctype = column["doctype"]
		fieldname = column["fieldname"]
		if column["issingle"]:
			predicates.append(
				"not exists ("
				"select 1 from `tabSingles` ref "
				f"where ref.`doctype` = {frappe.db.escape(doctype)} "
				f"and ref.`field` = {frappe.db.escape(fieldname)} "
				f"and ref.`value` = {blob}.`name`"
				")"
			)
		else:
			table = _quote_identifier(f"tab{doctype}")
			field = _quote_identifier(fieldname)
			predicates.append(
				f"not exists (select 1 from {table} ref where ref.{field} = {blob}.`name`)"
			)
	return "\n  and ".join(predicates) or "1 = 1"


def _quote_identifier(value: str) -> str:
	return f"`{value.replace('`', '``')}`"


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


def get_orphan_blobs(cutoff, limit: int, *, predicate: str | None = None) -> list[dict]:
	"""Blobs no discovered Link column references, untouched since ``cutoff``."""
	predicate = orphan_predicate() if predicate is None else predicate
	return frappe.db.sql(
		f"""
		select b.name, b.key, b.driver, b.is_private
		from `tabFile Blob` b
		where b.modified < %(cutoff)s
		  and {predicate}
		limit %(limit)s
		""",
		{"cutoff": cutoff, "limit": limit},
		as_dict=True,
	)


def delete_blob(blob, cutoff, logger, stats: dict, *, predicate: str | None = None) -> bool:
	"""Delete one blob's bytes, then its row. Return True when the row is gone.

	Re-verifies the orphan status under a row lock first: ``put_blob``'s
	dedup can revive a selected orphan concurrently (it locks the row and
	bumps ``modified``), and a new File row may have appeared since
	``get_orphan_blobs`` ran. Drivers treat a missing object as a no-op
	delete. On a driver error the row is kept so the next run retries."""
	if not is_still_orphan(blob.name, cutoff, predicate=predicate):
		return False

	try:
		driver = frappe.storage.get_driver(blob.driver)
		driver.delete(blob.key, is_private=bool(blob.is_private))
	except Exception:
		stats["bytes_delete_errors"] += 1
		logger.warning(
			f"storage gc: could not delete bytes of blob {blob.name} (key {blob.key})", exc_info=True
		)
		return False

	try:
		frappe.delete_doc("File Blob", blob.name, force=1, ignore_permissions=True, ignore_missing=True)
		logger.info(f"storage gc: deleted blob {blob.name} (key {blob.key}, driver {blob.driver})")
		return True
	except Exception:
		logger.warning(f"storage gc: could not delete File Blob row {blob.name}", exc_info=True)
		return False


def is_still_orphan(blob_name: str, cutoff, *, predicate: str | None = None) -> bool:
	"""Lock the blob row and re-check that it is still unreferenced and stale."""
	modified = frappe.db.get_value("File Blob", blob_name, "modified", for_update=True)
	if not modified or get_datetime(modified) >= get_datetime(cutoff):
		return False
	predicate = orphan_predicate() if predicate is None else predicate
	return bool(
		frappe.db.sql(
			f"""
			select b.name
			from `tabFile Blob` b
			where b.name = %(blob_name)s
			  and {predicate}
			""",
			{"blob_name": blob_name},
		)
	)


def expire_upload_sessions(logger) -> int:
	"""Sweep stale upload sessions. Guarded: the upload module is optional."""
	try:
		from frappe.storage.upload import expire_stale_upload_sessions
	except ImportError:
		return 0
	try:
		return expire_stale_upload_sessions() or 0
	except Exception:
		logger.warning("storage gc: expire_stale_upload_sessions failed", exc_info=True)
		return 0
