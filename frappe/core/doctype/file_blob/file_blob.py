# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import frappe
from frappe.model.document import Document


class FileBlob(Document):
	"""One stored object: checksum, size, driver, key.

	Immutable. Filenames, folders and attachment links live on File rows
	that point here through the ``blob`` link field."""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		checksum: DF.Data
		driver: DF.Data
		file_size: DF.Int
		is_private: DF.Check
		key: DF.Data
		mime_type: DF.Data | None
		status: DF.Literal["Pending", "Ready"]
	# end: auto-generated types


def on_doctype_update():
	# Best-effort DDL: index support differs across backends (site may be
	# sqlite); a failure must not break migrate.
	try:
		# the dedup invariant: one blob per content per privacy namespace
		# per driver. The key derives from the checksum (plus a filename
		# extension), so it cannot carry the unique constraint itself.
		frappe.db.add_unique(
			"File Blob", ["checksum", "is_private", "driver"], constraint_name="unique_file_blob_checksum"
		)
	except Exception:
		frappe.log_error(title="File Blob: could not create unique index on checksum")

	try:
		frappe.db.add_index("File Blob", ["key"])
	except Exception:
		frappe.log_error(title="File Blob: could not create index on key")
