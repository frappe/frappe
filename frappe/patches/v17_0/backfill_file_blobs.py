# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""Backfill File Blob rows for legacy File rows (Storage v2).

Runs only when the ``storage_v2`` site flag is on. To backfill later:
enable the flag, then run ``bench execute frappe.storage.backfill.run``.
"""

import frappe
import frappe.storage


def execute():
	if not frappe.storage.enabled():
		frappe.logger("storage").info(
			"storage_v2 is disabled; skipped the File Blob backfill. "
			"Enable the flag, then run 'bench execute frappe.storage.backfill.run'."
		)
		return

	from frappe.storage import backfill

	backfill.run()
