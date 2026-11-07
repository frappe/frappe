# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import io
from collections.abc import Iterator
from contextlib import contextmanager
from typing import IO

import frappe
from frappe.storage.driver import StorageDriver


class MemoryDriver(StorageDriver):
	"""Dict-backed driver for tests. No disk access."""

	name = "memory"

	def __init__(self):
		self.blobs: dict[tuple[bool, str], bytes] = {}

	def write(self, key: str, stream: IO[bytes], *, is_private: bool = False) -> None:
		self.blobs[(bool(is_private), key)] = stream.read()

	def read(self, key: str, *, is_private: bool = False) -> IO[bytes]:
		try:
			return io.BytesIO(self.blobs[(bool(is_private), key)])
		except KeyError:
			raise FileNotFoundError(key) from None

	def delete(self, key: str, *, is_private: bool = False) -> None:
		self.blobs.pop((bool(is_private), key), None)

	def exists(self, key: str, *, is_private: bool = False) -> bool:
		return (bool(is_private), key) in self.blobs


@contextmanager
def fake() -> Iterator[MemoryDriver]:
	"""Swap the active storage driver for an in-memory one.

	Usage::

	        with frappe.storage.fake() as store:
	            blob = put_blob(io.BytesIO(b"hello"), is_private=True)
	            assert store.exists(blob.key, is_private=True)

	The previous driver is restored on exit. No test touches
	``sites/<site>/public/files``."""
	previous = getattr(frappe.local, "storage_driver_override", None)
	driver = MemoryDriver()
	frappe.local.storage_driver_override = driver
	try:
		yield driver
	finally:
		frappe.local.storage_driver_override = previous
