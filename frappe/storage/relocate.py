# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""Resumable relocation of File Blob objects between storage drivers."""

from __future__ import annotations

from collections.abc import Callable

import frappe
from frappe.storage.blob import make_key
from frappe.storage.driver import StorageDriver, get_driver
from frappe.utils import cint

BATCH_SIZE = 100


def relocate_blobs(batch_size: int = BATCH_SIZE, target_driver: str | None = None) -> dict:
	"""Move blobs to a driver's canonical content-addressed keys.

	The configured storage driver is the default target. Rows are scanned in
	bounded, keyset-paginated batches, so a stopped run can safely be started
	again. The blob name never changes. Source objects are deleted only from an
	``after_commit`` callback once the row points at the copied object.
	"""
	if batch_size <= 0:
		frappe.throw("batch_size must be greater than zero", frappe.ValidationError)

	stats = {"moved": 0, "bytes": 0, "skipped": 0, "errors": 0}
	if not frappe.db.table_exists("File Blob"):
		return stats

	target = get_driver(target_driver)
	logger = frappe.logger("storage")
	after_name = ""

	while rows := get_relocation_batch(batch_size, after_name):
		moved_in_batch: list[tuple[str, int]] = []
		for row in rows:
			try:
				outcome = relocate_blob(row, target, stats, logger)
			except Exception:
				stats["errors"] += 1
				logger.warning(f"storage relocation: could not move blob {row.name}", exc_info=True)
				continue

			if outcome is None:
				stats["skipped"] += 1
			else:
				moved_in_batch.append((row.name, outcome))

		try:
			_commit_batch()
		except Exception:
			# The whole batch remains at its source rows. Canonical objects copied
			# before the failed commit are harmless and make the next run cheaper.
			frappe.db.rollback()
			stats["errors"] += len(moved_in_batch)
			for blob_name, _size in moved_in_batch:
				logger.warning(
					f"storage relocation: could not commit move of blob {blob_name}", exc_info=True
				)
		else:
			stats["moved"] += len(moved_in_batch)
			stats["bytes"] += sum(size for _blob_name, size in moved_in_batch)

		after_name = rows[-1].name

	logger.info(
		"storage relocation: moved {0} blobs ({1} bytes), skipped {2}, errors {3}".format(
			stats["moved"], stats["bytes"], stats["skipped"], stats["errors"]
		)
	)
	return stats


def get_relocation_batch(limit: int, after_name: str) -> list[dict]:
	"""Return the next stable page of blob rows."""
	return frappe.get_all(
		"File Blob",
		filters={"name": (">", after_name)},
		fields=["name", "key", "checksum", "file_size", "driver", "is_private"],
		order_by="name asc",
		limit=limit,
	)


def relocate_blob(row, target: StorageDriver, stats: dict, logger) -> int | None:
	"""Prepare one row move, returning its byte count or ``None`` when skipped."""
	target_key = make_key(row.checksum)
	if row.driver == target.name and row.key == target_key:
		return None

	source = get_driver(row.driver)
	is_private = bool(row.is_private)
	if not target.exists(target_key, is_private=is_private):
		with source.read(row.key, is_private=is_private) as stream:
			target.write(target_key, stream, is_private=is_private)

	savepoint = f"relocate_{frappe.generate_hash(length=10)}"
	frappe.db.savepoint(savepoint)
	try:
		locked = lock_blob(row.name)
		if not locked:
			frappe.db.release_savepoint(savepoint)
			return None

		if locked.driver == target.name and locked.key == target_key:
			frappe.db.release_savepoint(savepoint)
			return None

		if not _same_location(row, locked):
			raise RuntimeError("blob location changed while it was being copied")

		frappe.db.set_value(
			"File Blob",
			row.name,
			{"driver": target.name, "key": target_key},
			update_modified=False,
		)
		frappe.db.release_savepoint(savepoint)
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		raise

	frappe.db.after_commit.add(
		delete_source_after_commit(
			source,
			row.key,
			is_private,
			blob_name=row.name,
			stats=stats,
			logger=logger,
		)
	)
	return int(row.file_size or 0)


def lock_blob(blob_name: str) -> dict | None:
	"""Take the same File Blob row lock used by garbage collection."""
	return frappe.db.get_value(
		"File Blob",
		blob_name,
		["name", "key", "checksum", "file_size", "driver", "is_private"],
		as_dict=True,
		for_update=True,
	)


def delete_source_after_commit(
	source: StorageDriver,
	key: str,
	is_private: bool,
	*,
	blob_name: str,
	stats: dict,
	logger,
) -> Callable[[], None]:
	"""Build a defensive commit callback for one old object."""

	def delete_source() -> None:
		try:
			# A malformed or historical duplicate row may still own this object.
			# Keep the shared bytes rather than deleting another blob's location.
			if frappe.db.exists(
				"File Blob",
				{"driver": source.name, "key": key, "is_private": cint(is_private)},
			):
				return
			source.delete(key, is_private=is_private)
		except Exception:
			stats["errors"] += 1
			logger.warning(
				f"storage relocation: could not delete source bytes of blob {blob_name} (key {key})",
				exc_info=True,
			)

	return delete_source


def _same_location(selected, locked) -> bool:
	return all(
		getattr(selected, field) == getattr(locked, field)
		for field in ("key", "checksum", "driver", "is_private")
	)


def _commit_batch() -> None:
	"""Commit a production batch while preserving test transaction isolation."""
	if not frappe.flags.in_test:
		frappe.db.commit()  # batched job: committed pages make reruns resumable  # nosemgrep
