# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""Shared helpers for storage v2 tests."""

from contextlib import contextmanager
from unittest.mock import patch

import frappe

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def reset_file_controller():
	"""Drop the cached File controller for the current site.

	``File.resolve_controller`` picks FileV1 or FileV2 from the
	``storage_v2`` flag, and ``get_controller`` caches the result per site.
	A test that toggles the flag must invalidate that cache on the way in
	and on the way out."""
	frappe.controllers.get(frappe.local.site, {}).pop("File", None)


@contextmanager
def storage_v2(enabled: bool = True):
	"""Turn the storage_v2 site flag on or off for the duration of the block."""
	previous = frappe.conf.get("storage_v2")
	frappe.conf["storage_v2"] = 1 if enabled else 0
	reset_file_controller()
	try:
		yield
	finally:
		if previous is None:
			frappe.conf.pop("storage_v2", None)
		else:
			frappe.conf["storage_v2"] = previous
		reset_file_controller()


@contextmanager
def use_driver(driver):
	"""Swap the active storage driver for a custom one, like fake()."""
	previous = getattr(frappe.local, "storage_driver_override", None)
	frappe.local.storage_driver_override = driver
	try:
		yield driver
	finally:
		frappe.local.storage_driver_override = previous


@contextmanager
def hook_value(name: str, value):
	"""Pretend the installed apps registered ``value`` under hook ``name``."""
	real_get_hooks = frappe.get_hooks

	def get_hooks(hook=None, *args, **kwargs):
		if hook == name:
			return value
		return real_get_hooks(hook, *args, **kwargs)

	with patch("frappe.get_hooks", side_effect=get_hooks):
		yield


def file_permissions_enforced():
	"""Undo an installed app's ``ignore_file_permissions`` hook."""
	return hook_value("ignore_file_permissions", [])


def unique_bytes(prefix: bytes = b"storage-v2-test-") -> bytes:
	"""Unique bytes per call so blob reuse never collides across tests or runs."""
	return prefix + frappe.generate_hash(length=32).encode()


def unique_png() -> bytes:
	"""Unique bytes that sniff as PNG."""
	return unique_bytes(PNG_MAGIC)
