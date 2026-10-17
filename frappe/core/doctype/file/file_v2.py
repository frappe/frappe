# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Blob-native (storage v2) File implementation. See ``frappe/storage/SPEC.md``.

Compat shim: unbackfilled legacy rows (``blob`` is NULL) are read through
``FileV1``'s disk path. The shim goes with ``file_v1.py``."""

import io

import frappe
import frappe.storage
from frappe import _
from frappe.utils import cint

from .file import File
from .file_v1 import FileV1


class FileV2(File):
	def _ingest_new_content(self):
		if not self.get("blob") and not self.content and self.file_url:
			# a copied row (amend, attachment copy) carries only its file_url;
			# relink the blob instead of writing the bytes again
			self.adopt_blob_from_file_url()

		if self.flags.from_existing_blob:
			# the row points at an already stored blob; no bytes to write
			if not self.file_url:
				self.set_blob_file_url()
			return

		if self.is_remote_file:
			self.validate_remote_file()
			return

		self.save_file(content=self.get_content())

	def _store_content(self, ignore_existing_file_check=False, overwrite=False):
		"""Write ``self._content`` through the active driver. ``put_blob`` dedups, so the arguments are unused."""
		from frappe.storage.blob import validate_upload

		if isinstance(self._content, str):
			self._content = self._content.encode()
		self.check_content()
		blob = frappe.storage.put_blob(
			io.BytesIO(self._content),
			is_private=bool(self.is_private),
			filename=self.file_name,
		)
		# reject active content hidden under a mismatched extension, as upload sessions do
		validate_upload(blob, self.file_name)
		self.blob = blob.name
		self.flags.stored_blob = blob.name
		self.file_size = blob.file_size
		self.set_blob_file_url(blob)
		return {"file_name": self.file_name, "file_url": self.file_url}

	def before_save(self):
		super().before_save()
		self.enforce_blob_privacy()

	def enforce_blob_privacy(self):
		"""Point a blob-backed File at a blob in its own privacy namespace.

		Runs from before_save: a File subclass may override validate() without super()."""
		if self.is_folder or self.is_new() or not self.get("blob"):
			return
		blob_is_private = frappe.db.get_value("File Blob", self.blob, "is_private")
		if blob_is_private is None or cint(blob_is_private) == cint(self.is_private):
			return
		self.flip_blob_privacy()

	def handle_is_private_changed(self):
		# enforce_blob_privacy repoints a blob-backed row in before_save,
		# after its blob link is authorized
		if self.is_remote_file or self.get("blob"):
			return

		# validate() also lands here for docs rebuilt from a dict, where
		# has_value_changed() is True without a real change (no before-save
		# doc); only an actual privacy change repoints the blob
		if self.name and cint(self.is_private) == cint(frappe.db.get_value("File", self.name, "is_private")):
			return

		self.flip_blob_privacy()

	def flip_blob_privacy(self):
		"""Re-put the bytes into the other privacy namespace, repoint the row and its attachment field.

		The old blob is left for GC. An unbackfilled legacy row is adopted into
		blob storage; its disk file stays for other rows that share the URL."""
		old_file_url = self.file_url
		with self._open_stored_bytes() as stream:
			new_blob = frappe.storage.put_blob(
				stream,
				is_private=bool(cint(self.is_private)),
				filename=self.file_name,
			)
		self.blob = new_blob.name
		self.flags.stored_blob = new_blob.name
		self.set_blob_file_url(new_blob)
		self.update_attached_to_field(old_file_url)

	def adopt_blob_from_file_url(self):
		"""Set ``blob`` from the blob behind file_url: a blob URL, or a relocated v1 URL.

		A private blob is adopted only when the user can already download it,
		so knowing a URL does not grant access to the file."""
		from frappe.storage.serve import has_file_permission
		from frappe.storage.url import PRIVATE_PREFIX, parse_blob_url

		if parsed := parse_blob_url(self.file_url):
			is_private, blob_name, _filename = parsed
		else:
			is_private = self.file_url.startswith(PRIVATE_PREFIX)
			blob_name = frappe.db.get_value(
				"File",
				{"file_url": self.file_url, "is_private": cint(is_private), "blob": ("is", "set")},
				"blob",
			)
		if not blob_name or not frappe.db.exists(
			"File Blob", {"name": blob_name, "is_private": cint(is_private)}
		):
			return
		if is_private and not self.flags.ignore_permissions and not has_file_permission(blob_name):
			frappe.throw(_("You don't have permission to access this file"), frappe.PermissionError)
		self.blob = blob_name
		self.is_private = cint(is_private)
		self.flags.from_existing_blob = True
		if parsed:
			self.set_blob_file_url()

	def set_blob_file_url(self, blob=None):
		"""Regenerate file_url from the linked blob. Stable and unsigned."""
		from frappe.storage.url import blob_url

		if blob is None:
			blob = frappe.get_doc("File Blob", self.blob)
		self.file_url = blob_url(blob)

	def validate_file_path(self):
		if self.is_remote_file:
			return

		if self.get("blob"):
			# the bytes come from the blob key, which the driver confines to
			# the files directory; file_url is still served and looked up
			if self.file_url and ".." in self.file_url.split("/"):
				frappe.throw(_("The File URL you've entered is incorrect"), title=_("Invalid File URL"))
			return

		FileV1.validate_file_path(self)  # compat shim: unbackfilled legacy row

	def validate_file_url(self):
		if self.is_remote_file or not self.file_url:
			return

		if not self.get("blob"):
			FileV1.validate_file_url(self)  # compat shim: unbackfilled legacy row
			return

		# blob URLs and backfilled legacy URLs share these two prefixes
		if not self.file_url.startswith(("/files/", "/private/files/")):
			frappe.throw(
				_("The File URL you've entered is incorrect"),
				title=_("Invalid File URL"),
			)

	def validate_file_on_disk(self):
		"""Validate that the stored bytes exist."""
		if not self.get("blob"):
			return FileV1.validate_file_on_disk(self)  # compat shim: unbackfilled legacy row

		if not self.exists_on_disk():
			frappe.throw(_("File {0} does not exist").format(self.file_url), IOError)
		return True

	def exists_on_disk(self):
		if not self.get("blob"):
			return FileV1.exists_on_disk(self)  # compat shim: unbackfilled legacy row

		blob = frappe.get_doc("File Blob", self.blob)
		driver = frappe.storage.get_driver(blob.driver)
		return driver.exists(blob.key, is_private=bool(blob.is_private))

	def _read_content(self) -> bytes:
		with self._open_stored_bytes() as f:
			return f.read()

	def _open_stored_bytes(self):
		"""Readable binary stream of the stored bytes, through the driver."""
		if not self.get("blob"):
			# compat shim: unbackfilled legacy row, read from its disk path
			# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
			return open(self.get_full_path(), mode="rb")

		blob = frappe.get_doc("File Blob", self.blob)
		driver = frappe.storage.get_driver(blob.driver)
		return driver.read(blob.key, is_private=bool(blob.is_private))

	def get_full_path(self):
		"""Real disk path of the stored bytes (local driver only)."""
		if not self.get("blob"):
			return FileV1.get_full_path(self)  # compat shim: unbackfilled legacy row

		from frappe.storage.local_driver import LocalDriver

		blob = frappe.get_doc("File Blob", self.blob)
		driver = frappe.storage.get_driver(blob.driver)
		if not isinstance(driver, LocalDriver):
			frappe.throw(
				_("File {0} is stored in the {1} storage driver and has no local file path").format(
					self.name, blob.driver
				)
			)
		return driver.get_path(blob.key, bool(blob.is_private))

	def _delete_file_on_disk(self):
		"""Leave blob bytes to GC; delete an unbackfilled legacy file once no row uses its URL."""
		if self.get("blob"):
			return
		if frappe.db.exists("File", {"file_url": self.file_url, "name": ("!=", self.name)}):
			return

		from frappe.storage.backfill import locate

		if located := locate(self.file_url or ""):
			is_private, rel_path = located
			# a backfilled blob keeps its legacy path as key and may serve other rows
			if frappe.db.exists("File Blob", {"driver": "local", "key": rel_path, "is_private": is_private}):
				return
		FileV1.delete_file_from_filesystem(self)  # compat shim: unbackfilled legacy row
