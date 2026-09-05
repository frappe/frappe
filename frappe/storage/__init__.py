# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""File Storage v2 public API.

Behind the ``storage_v2`` site config flag. See ``frappe/storage/driver.py``
for the driver interface and registry.
"""

import frappe
from frappe.storage.blob import put_blob
from frappe.storage.driver import get_driver
from frappe.storage.memory_driver import fake
from frappe.storage.url import signed_url

__all__ = ["enabled", "fake", "get_driver", "put_blob", "signed_url"]


def enabled() -> bool:
	"""Return True if File Storage v2 is enabled for the current site."""
	return bool(frappe.conf.storage_v2)
