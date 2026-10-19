# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import io
from abc import ABC, abstractmethod
from typing import IO

import frappe
from frappe import _

# Built-in drivers shipped with the framework.
BUILTIN_DRIVERS = {
	"local": "frappe.storage.local_driver.LocalDriver",
	"memory": "frappe.storage.memory_driver.MemoryDriver",
	"s3": "frappe.storage.s3_driver.S3Driver",
}

DEFAULT_DRIVER = "local"


class StorageDriver(ABC):
	"""Read, write, delete and check bytes by key.

	Keys carry no privacy, so each method takes ``is_private`` to pick the namespace."""

	name: str

	# Prepended to every new key. A driver shared by several sites (such as
	# one S3 bucket) sets it to keep each site's objects apart.
	key_prefix: str = ""

	@abstractmethod
	def write(self, key: str, stream: IO[bytes], *, is_private: bool = False) -> None: ...

	@abstractmethod
	def read(self, key: str, *, is_private: bool = False) -> IO[bytes]:
		"""Return a readable binary stream. Never the full bytes."""

	@abstractmethod
	def delete(self, key: str, *, is_private: bool = False) -> None: ...

	@abstractmethod
	def exists(self, key: str, *, is_private: bool = False) -> bool: ...

	def read_range(self, key: str, start: int, end: int | None, *, is_private: bool = False) -> IO[bytes]:
		"""Return bytes from *start* through inclusive *end*. The default reads the whole object."""
		stream = self.read(key, is_private=is_private)
		try:
			content = stream.read()
		finally:
			stream.close()
		return io.BytesIO(content[start : None if end is None else end + 1])

	def download_url(
		self,
		key: str,
		filename: str,
		expires_in: int,
		*,
		is_private: bool = False,
		mime_type: str | None = None,
		as_attachment: bool = False,
	) -> str | None:
		"""Native signed URL (e.g. S3 presigned GET), else None and Frappe serves the bytes.

		The URL must serve the type and disposition ``frappe.storage.blob.served_type`` gives."""
		return None

	def upload_target(self, key: str, size: int, *, is_private: bool = False) -> dict | None:
		"""Native direct-upload target (e.g. S3 presigned POST).

		None means: the client sends chunks through the upload session."""
		return None


def get_driver_classes() -> dict[str, str]:
	"""Return the driver registry, name -> dotted class path, with ``storage_drivers`` hook overrides."""
	drivers = dict(BUILTIN_DRIVERS)
	hooked = frappe.get_hooks("storage_drivers") or {}
	for name, path in hooked.items():
		# dict hooks collect one value per app; the last app wins
		drivers[name] = path[-1] if isinstance(path, list) else path
	return drivers


def get_driver(name: str | None = None) -> StorageDriver:
	"""Return a driver instance by name, cached per request.

	With no name, the active driver: the ``fake()`` override, else the ``storage_driver`` site config."""
	override = getattr(frappe.local, "storage_driver_override", None)
	if override is not None and (name is None or name == override.name):
		return override
	if name is None:
		name = frappe.conf.storage_driver or DEFAULT_DRIVER

	if not hasattr(frappe.local, "storage_driver_instances"):
		frappe.local.storage_driver_instances = {}
	cache = frappe.local.storage_driver_instances

	if name not in cache:
		classes = get_driver_classes()
		if name not in classes:
			frappe.throw(_("Unknown storage driver: {0}").format(name))
		cache[name] = frappe.get_attr(classes[name])()

	return cache[name]
