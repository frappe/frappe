# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""Local disk cache for blobs on remote drivers. See "Local cache" in SPEC.md."""

import contextlib
import os
import shutil
from typing import TYPE_CHECKING

import frappe
from frappe.storage.blob import key_basename, make_key
from frappe.storage.driver import get_driver
from frappe.storage.local_driver import LocalDriver
from frappe.utils import cint

if TYPE_CHECKING:
	from frappe.core.doctype.file_blob.file_blob import FileBlob

CHUNK_SIZE = 64 * 1024
CACHE_JOB_TIMEOUT = 3600


def is_cache_enabled(blob: "FileBlob") -> bool:
	"""True when the ``storage_local_cache`` site flag is on and the blob's driver caches."""
	return bool(frappe.conf.storage_local_cache) and get_driver(blob.driver).cache_locally


def get_max_cached_file_size() -> int:
	"""Largest blob to cache, in bytes, from System Settings. 0 caches nothing."""
	return cint(frappe.get_system_settings("max_cached_file_size")) * 1024 * 1024


def get_cache_key(blob: "FileBlob") -> str:
	"""Local key of a blob, ``<blob>/<filename>``: the path its URL maps to, so nginx serves a public one."""
	return make_key(LocalDriver(), blob.name, key_basename(blob.key))


def get_cache_path(blob: "FileBlob") -> str:
	"""Cache file of a blob. Blobs are immutable, so a cached file never goes stale."""
	return LocalDriver().get_path(get_cache_key(blob), bool(blob.is_private))


def get_cached_path(blob: "FileBlob") -> str | None:
	"""Path of the blob's cached file, or None when caching is off or the file is missing."""
	if not is_cache_enabled(blob):
		return None
	path = get_cache_path(blob)
	return path if os.path.isfile(path) else None


def queue_cache(blob: "FileBlob") -> None:
	"""Queue a background download of a blob within the size limit. One job runs per blob at a time."""
	if not is_cache_enabled(blob) or int(blob.file_size or 0) > get_max_cached_file_size():
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
	"""Download a blob from its driver into the cache. Skip a blob that is cached or deleted since queued."""
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
		os.replace(part, path)
	finally:
		with contextlib.suppress(FileNotFoundError):
			os.remove(part)


def delete_cached(blob: "FileBlob") -> None:
	LocalDriver().delete(get_cache_key(blob), is_private=bool(blob.is_private))
