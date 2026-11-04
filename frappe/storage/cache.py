# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""Local disk cache for blobs on remote drivers. See "Local cache" in SPEC.md."""

import contextlib
import os
import shutil
import time
import zlib
from collections.abc import Iterator
from typing import TYPE_CHECKING

import frappe
from frappe.storage.blob import key_basename, make_key
from frappe.storage.driver import get_driver, get_driver_classes
from frappe.storage.local_driver import LocalDriver
from frappe.utils import cint
from frappe.utils.file_lock import LockTimeoutError
from frappe.utils.synchronization import filelock

if TYPE_CHECKING:
	from frappe.core.doctype.file_blob.file_blob import FileBlob

CHUNK_SIZE = 64 * 1024
CACHE_JOB_TIMEOUT = 3600
LOCK_STRIPES = 64
RESTORE_LOCK_TIMEOUT = 5
DELETE_LOCK_TIMEOUT = 30
SWEEP_LOCK_TIMEOUT = 1
SWEEP_LOCK = "storage_cache_sweep"
NAME_BATCH_SIZE = 1000
LOCAL_CACHE_DEFAULTS = {"max_file_size_mb": 100, "keep_minutes": 300, "grace_minutes": 60}


def get_holding_dir() -> str:
	return frappe.get_site_path("private", "cache", "expiring")


class HoldingDriver(LocalDriver):
	"""Holding folder of expiring cache copies: the local layout under ``private/cache/expiring``."""

	def get_files_dir(self, is_private: bool = False) -> str:
		return os.path.join(get_holding_dir(), "private" if is_private else "public")


def cache_lock(blob_name: str, timeout: float):
	"""Lock one of a fixed set of lock files, so a site never holds one per blob."""
	return filelock(f"storage_cache_{zlib.crc32(blob_name.encode()) % LOCK_STRIPES}", timeout=timeout)


def sweep_lock(timeout: float):
	"""Lock held by the sweep and by a blob relocation, so the sweep never lists a row that is moving."""
	return filelock(SWEEP_LOCK, timeout=timeout)


def is_cache_enabled(blob: "FileBlob") -> bool:
	"""True when the ``storage_local_cache`` site flag is on and the blob's driver caches."""
	return bool(frappe.conf.storage_local_cache) and get_driver(blob.driver).cache_locally


def is_cacheable(blob: "FileBlob") -> bool:
	"""True when a request for the blob queues a download: caching is on and the blob fits the size limit."""
	return is_cache_enabled(blob) and int(blob.file_size or 0) <= get_max_cached_file_size()


def get_cache_setting(name: str) -> int:
	"""A ``storage_local_cache_config`` value from site config, else its default."""
	config = frappe.conf.storage_local_cache_config or {}
	return cint(config.get(name, LOCAL_CACHE_DEFAULTS[name]))


def get_max_cached_file_size() -> int:
	"""Largest blob to cache, in bytes. 0 caches nothing."""
	return get_cache_setting("max_file_size_mb") * 1024 * 1024


def get_cache_key(blob: "FileBlob") -> str:
	"""Local key of a blob, ``<blob>/<filename>``: the path its URL maps to, so nginx serves a public one."""
	return make_key(LocalDriver(), blob.name, key_basename(blob.key))


def get_cache_path(blob: "FileBlob") -> str:
	"""Cache file of a blob. Blobs are immutable, so a cached file never goes stale."""
	return LocalDriver().get_path(get_cache_key(blob), bool(blob.is_private))


def get_holding_path(blob: "FileBlob") -> str:
	return HoldingDriver().get_path(get_cache_key(blob), bool(blob.is_private))


def get_cached_path(blob: "FileBlob") -> str | None:
	"""Path of the blob's cached file, restored from the holding folder when it is there.

	None when caching is off or no copy exists."""
	if not is_cache_enabled(blob):
		return None
	path = get_cache_path(blob)
	return path if os.path.isfile(path) else restore_cached(blob)


def restore_cached(blob: "FileBlob") -> str | None:
	"""Move a held copy back into the cache and restart its clock. None when there is no copy to move."""
	holding_path = get_holding_path(blob)
	if not os.path.isfile(holding_path):
		return None

	path = get_cache_path(blob)
	try:
		with cache_lock(blob.name, RESTORE_LOCK_TIMEOUT):
			os.makedirs(os.path.dirname(path), exist_ok=True)
			shutil.move(holding_path, path)
			os.utime(path)
			remove_empty_folder(holding_path)
	except (FileNotFoundError, LockTimeoutError):
		return None
	return path


def remove_empty_folder(path: str) -> None:
	"""Remove the blob folder that held ``path`` when nothing else is in it."""
	with contextlib.suppress(OSError):
		os.rmdir(os.path.dirname(path))


def queue_cache(blob: "FileBlob") -> None:
	"""Queue a background download of a blob within the size limit. One job runs per blob at a time."""
	if not is_cacheable(blob):
		return
	frappe.enqueue(
		"frappe.storage.cache.cache_blob",
		queue="long",
		timeout=CACHE_JOB_TIMEOUT,
		job_id=f"storage_cache::{blob.name}",
		deduplicate=True,
		blob_name=blob.name,
	)


def cache_blob(blob_name: str) -> None:
	"""Download a blob from its driver into the cache. Skip a blob that is cached or deleted since queued.

	The row is read again with a lock before the file lands, so a blob that GC deleted during the
	download leaves no file that no row owns."""
	if not frappe.db.exists("File Blob", blob_name):
		return
	blob = frappe.get_doc("File Blob", blob_name)
	path = get_cache_path(blob)
	if os.path.isfile(path):
		return

	os.makedirs(os.path.dirname(path), exist_ok=True)
	part = f"{path}.{frappe.generate_hash(length=8)}.part"
	driver = get_driver(blob.driver)
	try:
		with (
			contextlib.closing(driver.read(blob.key, is_private=bool(blob.is_private))) as stream,
			open(part, "wb") as file,
		):
			shutil.copyfileobj(stream, file, CHUNK_SIZE)
		if os.path.getsize(part) != int(blob.file_size or 0):
			raise OSError(f"Cached {blob.name} has {os.path.getsize(part)} bytes, expected {blob.file_size}")
		if frappe.db.get_value("File Blob", blob_name, "name", for_update=True):
			os.replace(part, path)
	finally:
		with contextlib.suppress(FileNotFoundError):
			os.remove(part)
		remove_empty_folder(path)


def delete_cached(blob: "FileBlob") -> None:
	"""Delete a blob's cached copy and its held copy, under the blob's lock so no restore runs in between."""
	with cache_lock(blob.name, DELETE_LOCK_TIMEOUT):
		for driver in (LocalDriver(), HoldingDriver()):
			driver.delete(get_cache_key(blob), is_private=bool(blob.is_private))


def sweep_cache() -> dict:
	"""Hold cached copies older than ``keep_minutes``, then delete held copies older than ``grace_minutes``.

	A copy leaves ``public/files`` when it is held, so a request for it reaches Python and restores it.
	Skips the run while a relocation holds the lock. The lock comes before any database read, so the
	listing sees every relocation commit."""
	try:
		with sweep_lock(SWEEP_LOCK_TIMEOUT):
			now = time.time()
			keep = get_cache_setting("keep_minutes") * 60
			grace = get_cache_setting("grace_minutes") * 60
			held = sum(hold_copy(blob, now - keep) for blob in get_cached_copies())
			return {"held": held, "deleted": delete_held_copies(now - grace)}
	except LockTimeoutError:
		return {"held": 0, "deleted": 0}


def get_cached_copies() -> Iterator[frappe._dict]:
	"""File Blob rows of caching drivers that have a folder in the files folders.

	A local blob has the same path shape as a cached copy, so the row's driver tells them apart.
	A site with no blob on a caching driver never scans its files folders."""
	drivers = [name for name, path in get_driver_classes().items() if frappe.get_attr(path).cache_locally]
	if not (drivers and frappe.db.exists("File Blob", {"driver": ("in", drivers)})):
		return
	for is_private in (0, 1):
		files_dir = LocalDriver().get_files_dir(bool(is_private))
		if not os.path.isdir(files_dir):
			continue
		names = [entry.name for entry in os.scandir(files_dir) if entry.is_dir(follow_symlinks=False)]
		for start in range(0, len(names), NAME_BATCH_SIZE):
			yield from frappe.get_all(
				"File Blob",
				filters={
					"name": ("in", names[start : start + NAME_BATCH_SIZE]),
					"driver": ("in", drivers),
					"is_private": is_private,
				},
				fields=["name", "key", "is_private"],
			)


def hold_copy(blob: "FileBlob", cutoff: float) -> bool:
	"""Move one cached copy last written before ``cutoff`` into the holding folder."""
	path = get_cache_path(blob)
	try:
		with cache_lock(blob.name, SWEEP_LOCK_TIMEOUT):
			if os.path.getmtime(path) > cutoff:
				return False
			holding_path = get_holding_path(blob)
			os.makedirs(os.path.dirname(holding_path), exist_ok=True)
			shutil.move(path, holding_path)
			os.utime(holding_path)
			remove_empty_folder(path)
	except (FileNotFoundError, LockTimeoutError):
		return False
	return True


def delete_held_copies(cutoff: float) -> int:
	deleted = 0
	for folder, _subfolders, names in os.walk(get_holding_dir()):
		for name in names:
			deleted += delete_held_copy(os.path.join(folder, name), os.path.basename(folder), cutoff)
	return deleted


def delete_held_copy(path: str, blob_name: str, cutoff: float) -> bool:
	"""Delete one held copy last written before ``cutoff``."""
	try:
		with cache_lock(blob_name, SWEEP_LOCK_TIMEOUT):
			if os.path.getmtime(path) > cutoff:
				return False
			os.remove(path)
			remove_empty_folder(path)
	except (FileNotFoundError, LockTimeoutError):
		return False
	return True
