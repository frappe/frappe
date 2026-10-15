# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import frappe
from frappe.database.utils import drop_index_if_exists


def execute():
	"""Drop the unique index on File Blob ``(checksum, is_private, driver)``.

	Duplicate blobs are allowed; ``checksum`` keeps a plain index for the
	dedup lookup."""
	if frappe.db.table_exists("File Blob"):
		drop_index_if_exists("tabFile Blob", "unique_file_blob_checksum")
