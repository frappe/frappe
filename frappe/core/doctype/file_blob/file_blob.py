# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
from frappe.model.document import Document


class FileBlob(Document):
	"""One stored object: checksum, size, driver, key.

	Immutable. Filenames, folders and attachment links live on File rows
	that point here through the ``blob`` link field. Identical content
	usually shares one blob, but duplicates are allowed: ``put_blob``'s
	dedup is a best-effort lookup on the indexed ``checksum``."""

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
