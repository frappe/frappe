# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import frappe
from frappe import _
from frappe.storage.relocate import relocate_blobs


def execute():
	if not frappe.db.table_exists("File Blob") or not frappe.db.exists("File Blob", {"driver": "s3"}):
		return

	stats = relocate_blobs(target_driver="s3", source_driver="s3")
	if stats["errors"]:
		frappe.throw(
			_("S3 blob migration failed. Check the storage log and rerun the migration."),
			title=_("S3 Blob Migration Failed"),
		)
