# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""Resumable relocation of File Blob objects between storage drivers."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import NamedTuple

import frappe
from frappe import _
from frappe.storage.blob import key_basename, make_key, other_site_key_criterion
from frappe.storage.cache import sweep_lock
from frappe.storage.driver import StorageDriver, get_driver
from frappe.storage.s3_driver import S3Driver
from frappe.utils import cint

BATCH_SIZE = 100
SWEEP_WAIT_TIMEOUT = 600
RELOCATE_WORKERS = 16


class RelocationPlan(NamedTuple):
	row: dict
	source: StorageDriver
	target: StorageDriver
	target_key: str


def relocate_renamed_site_blobs() -> dict:
	"""Move blobs still stored under a former site name to this site's prefix. Safe to re-run.

	Copies only inside this site's bucket. The old objects stay: the driver refuses deletes outside
	this site's prefix, so backups taken before the rename still restore."""
	if get_driver().name != "s3":
		return {"moved": 0, "bytes": 0, "skipped": 0, "errors": 0}
	return relocate_blobs(target_driver="s3", source_driver="s3", from_other_sites=True)


def relocate_blobs(
	batch_size: int = BATCH_SIZE,
	target_driver: str | None = None,
	source_driver: str | None = None,
	from_other_sites: bool = False,
) -> dict:
	"""Move blobs to a driver's canonical ``<blob>/<filename>`` keys. Safe to re-run.

	The target defaults to the configured driver. ``File.file_url`` never changes.
	A source object is deleted only after the commit that repoints its row. Holds the cache sweep's
	lock for the whole run: a cached copy can become the target, and the sweep must not expire it.
	``from_other_sites`` moves only keys under another site's prefix, and only inside the same bucket."""
	if batch_size <= 0:
		frappe.throw(_("batch_size must be greater than zero"), frappe.ValidationError)

	stats = {"moved": 0, "bytes": 0, "skipped": 0, "errors": 0}
	if not frappe.db.table_exists("File Blob"):
		return stats

	target = get_driver(target_driver)
	logger = frappe.logger("storage")
	after_name = ""

	with sweep_lock(SWEEP_WAIT_TIMEOUT):
		while rows := get_relocation_batch(batch_size, after_name, source_driver, from_other_sites):
			moved_in_batch = relocate_batch(rows, target, stats, logger, same_bucket_only=from_other_sites)
			try:
				_commit_batch()
			except Exception:
				# The whole batch remains at its source rows. Canonical objects copied
				# before the failed commit are harmless and make the next run cheaper.
				frappe.db.rollback()
				stats["errors"] += len(moved_in_batch)
				logger.warning(
					f"storage relocation: could not commit the move of {len(moved_in_batch)} blobs",
					exc_info=True,
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


def get_relocation_batch(
	limit: int, after_name: str, source_driver: str | None = None, from_other_sites: bool = False
) -> list[dict]:
	"""Return the next stable page of blob rows."""
	blob = frappe.qb.DocType("File Blob")
	query = (
		frappe.qb.from_(blob)
		.select(blob.name, blob.key, blob.checksum, blob.file_size, blob.driver, blob.is_private)
		.where(blob.name > after_name)
		.orderby(blob.name)
		.limit(limit)
	)
	if source_driver is not None:
		query = query.where(blob.driver == source_driver)
	if from_other_sites:
		query = query.where(other_site_key_criterion(blob))
	return query.run(as_dict=True)


def relocate_batch(rows: list[dict], target: StorageDriver, stats: dict, logger, *, same_bucket_only: bool):
	"""Copy a page of blobs, then repoint each copied row. Return (blob name, size) per moved row."""
	plans = plan_batch(rows, target, stats, logger)
	moved = []
	for plan, copied in zip(plans, copy_blobs(plans, same_bucket_only), strict=True):
		try:
			# a copy thread's error, raised here so count_error logs its traceback
			if isinstance(copied, Exception):
				raise copied
			outcome = repoint_blob(plan, stats, logger) if copied else None
		except Exception:
			count_error(stats, logger, plan.row)
			continue
		if outcome is None:
			stats["skipped"] += 1
		else:
			moved.append((plan.row.name, outcome))
	return moved


def plan_batch(rows: list[dict], target: StorageDriver, stats: dict, logger) -> list[RelocationPlan]:
	"""The rows that still have to move, with their source driver and target key."""
	plans = []
	for row in rows:
		try:
			plan = plan_relocation(row, target)
		except Exception:
			count_error(stats, logger, row)
			continue
		if plan is None:
			stats["skipped"] += 1
		else:
			plans.append(plan)
	return plans


def count_error(stats: dict, logger, row) -> None:
	stats["errors"] += 1
	logger.warning(f"storage relocation: could not move blob {row.name}", exc_info=True)


def plan_relocation(row, target: StorageDriver) -> RelocationPlan | None:
	"""Where one row moves to, or ``None`` when it is already there."""
	target_key = make_key(target, row.name, key_basename(row.key))
	if row.driver == target.name and row.key == target_key:
		return None
	return RelocationPlan(row, get_driver(row.driver), target, target_key)


def copy_blobs(plans: list[RelocationPlan], same_bucket_only: bool) -> list[bool | Exception]:
	"""Copy each planned object; per plan, whether it is in place, or the copy error."""

	def copy(plan: RelocationPlan) -> bool | Exception:
		try:
			return copy_blob(plan, same_bucket_only=same_bucket_only)
		except Exception as error:
			return error

	# other drivers read frappe.local, which worker threads do not have
	if not all(is_same_bucket(plan.source, plan.target) for plan in plans):
		return [copy(plan) for plan in plans]
	with ThreadPoolExecutor(max_workers=RELOCATE_WORKERS) as pool:
		return list(pool.map(copy, plans))


def is_same_bucket(source: StorageDriver, target: StorageDriver) -> bool:
	"""Whether S3 can copy between the two drivers without the bytes leaving the bucket."""
	return (
		isinstance(source, S3Driver)
		and isinstance(target, S3Driver)
		and source.client is target.client
		and source.bucket == target.bucket
	)


def copy_blob(plan: RelocationPlan, same_bucket_only: bool = False) -> bool:
	"""Put the blob's bytes at its target key. False when ``same_bucket_only`` rules the copy out."""
	row, source, target, target_key = plan
	is_private = bool(row.is_private)
	if not target.exists(target_key, is_private=is_private):
		if is_same_bucket(source, target):
			if same_bucket_only and not source.exists(row.key, is_private=is_private):
				return False
			target.client.copy(
				CopySource={"Bucket": source.bucket, "Key": source.object_key(row.key, is_private)},
				Bucket=target.bucket,
				Key=target.object_key(target_key, is_private),
			)
		elif same_bucket_only:
			return False
		else:
			with source.read(row.key, is_private=is_private) as stream:
				target.write(target_key, stream, is_private=is_private)
	# the source is deleted after commit, so the copy must be in place first
	if not target.exists(target_key, is_private=is_private):
		raise RuntimeError(f"copied object {target_key} is missing")
	return True


def repoint_blob(plan: RelocationPlan, stats: dict, logger) -> int | None:
	"""Point the row at its copied object, returning its byte count or ``None`` when skipped."""
	row, source, target, target_key = plan
	is_private = bool(row.is_private)
	locked = lock_blob(row.name)
	if not locked:
		# GC deleted the row during the copy. The target key holds the blob
		# name, so no other blob can own the copy.
		target.delete(target_key, is_private=is_private)
		return None

	savepoint = f"relocate_{frappe.generate_hash(length=10)}"
	frappe.db.savepoint(savepoint)
	try:
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

	frappe.db.after_commit.add(delete_source_after_commit(source, row, stats, logger))
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


def delete_source_after_commit(source: StorageDriver, row, stats: dict, logger) -> Callable[[], None]:
	"""Build a commit callback that deletes a moved blob's old object."""
	is_private = bool(row.is_private)

	def delete_source() -> None:
		try:
			# a historical duplicate row may still own this object; keep its bytes
			if frappe.db.exists(
				"File Blob",
				{"driver": source.name, "key": row.key, "is_private": cint(is_private)},
			):
				return
			source.delete(row.key, is_private=is_private)
		except Exception:
			stats["errors"] += 1
			logger.warning(
				f"storage relocation: could not delete source bytes of blob {row.name} (key {row.key})",
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
