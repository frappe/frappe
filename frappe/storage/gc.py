# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""Garbage collection for Storage v2.

Deleting a File row never touches bytes synchronously; this daily job
does. A blob is garbage when no File row references it and it is older
than ``MIN_AGE_HOURS``. That covers rolled-back writes and stale
``Pending`` blobs from aborted uploads. Stale upload sessions are swept
through ``frappe.storage.upload.expire_stale_upload_sessions``.
"""

import frappe
import frappe.storage
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

	while True:
		orphans = get_orphan_blobs(cutoff, batch_size)
		deleted = 0
		for blob in orphans:
			if delete_blob(blob, cutoff, logger, stats):
				deleted += 1
		stats["blobs_deleted"] += deleted
		if not frappe.flags.in_test:
			# release the row locks taken by delete_blob's re-check
			frappe.db.commit()
		if deleted == 0 or len(orphans) < batch_size:
			break

	stats["upload_sessions_expired"] = expire_upload_sessions(logger)

	if stats["blobs_deleted"] or stats["upload_sessions_expired"]:
		logger.info(
			"storage gc: deleted {0} blobs, expired {1} upload sessions".format(
				stats["blobs_deleted"], stats["upload_sessions_expired"]
			)
		)
	return stats


def get_orphan_blobs(cutoff, limit: int) -> list[dict]:
	"""Blobs no File row references, untouched since ``cutoff``."""
	Blob = frappe.qb.DocType("File Blob")
	File = frappe.qb.DocType("File")
	return (
		frappe.qb.from_(Blob)
		.left_join(File)
		.on(File.blob == Blob.name)
		.select(Blob.name, Blob.key, Blob.driver, Blob.is_private)
		.where(File.name.isnull())
		.where(Blob.modified < cutoff)
		.limit(limit)
	).run(as_dict=True)


def delete_blob(blob, cutoff, logger, stats: dict) -> bool:
	"""Delete one blob's bytes, then its row. Return True when the row is gone.

	Re-verifies the orphan status under a row lock first: ``put_blob``'s
	dedup can revive a selected orphan concurrently (it locks the row and
	bumps ``modified``), and a new File row may have appeared since
	``get_orphan_blobs`` ran. Drivers treat a missing object as a no-op
	delete. On a driver error the row is kept so the next run retries."""
	if not is_still_orphan(blob.name, cutoff):
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


def is_still_orphan(blob_name: str, cutoff) -> bool:
	"""Lock the blob row and re-check that it is still unreferenced and stale."""
	modified = frappe.db.get_value("File Blob", blob_name, "modified", for_update=True)
	if not modified or get_datetime(modified) >= get_datetime(cutoff):
		return False
	return not frappe.db.exists("File", {"blob": blob_name})


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
