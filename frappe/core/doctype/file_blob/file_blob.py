# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import os

from frappe.model.document import Document
from frappe.storage.cache import get_cache_path
from frappe.storage.local_driver import LocalDriver


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
		is_on_disk: DF.Check
		is_private: DF.Check
		key: DF.Data
		mime_type: DF.Data | None
		status: DF.Literal["Pending", "Ready"]
	# end: auto-generated types

	@property
	def is_on_disk(self) -> bool:
		"""True when the bytes are on this site's disk: a local blob's file, or a cached copy.

		A held copy is not served, so it does not count. A new blob has no key yet."""
		if not (self.name and self.key):
			return False
		if self.driver == LocalDriver.name:
			return LocalDriver().exists(self.key, is_private=bool(self.is_private))
		return os.path.isfile(get_cache_path(self))
