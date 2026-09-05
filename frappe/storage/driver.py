# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
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

	Every byte access in Storage v2 goes through a driver. Keys are
	content-addressed (see ``frappe.storage.blob.make_key``) and carry no
	privacy information, so each method takes ``is_private`` to pick the
	public or private namespace.
	"""

	name: str

	@abstractmethod
	def write(self, key: str, stream: IO[bytes], *, is_private: bool = False) -> None: ...

	@abstractmethod
	def read(self, key: str, *, is_private: bool = False) -> IO[bytes]:
		"""Return a readable binary stream. Never the full bytes."""

	@abstractmethod
	def delete(self, key: str, *, is_private: bool = False) -> None: ...

	@abstractmethod
	def exists(self, key: str, *, is_private: bool = False) -> bool: ...

	def download_url(
		self, key: str, filename: str, expires_in: int, *, is_private: bool = False
	) -> str | None:
		"""Native signed URL (e.g. S3 presigned GET).

		None means: the framework serves the bytes itself."""
		return None

	def upload_target(self, key: str, size: int, *, is_private: bool = False) -> dict | None:
		"""Native direct-upload target (e.g. S3 presigned POST).

		None means: client must use the framework upload endpoint."""
		return None


def get_driver_classes() -> dict[str, str]:
	"""Return the driver registry: name -> dotted class path.

	Built-in drivers, overridable through the ``storage_drivers`` hook."""
	drivers = dict(BUILTIN_DRIVERS)
	hooked = frappe.get_hooks("storage_drivers") or {}
	for name, path in hooked.items():
		# dict hooks collect one value per app; the last app wins
		drivers[name] = path[-1] if isinstance(path, list) else path
	return drivers


def get_driver(name: str | None = None) -> StorageDriver:
	"""Return a driver instance by name.

	With no name, return the active driver for the site: the ``fake()``
	override if set, else the ``storage_driver`` site config (default
	``local``). Instances are cached per request/site context."""
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
