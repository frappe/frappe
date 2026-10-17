# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Blob-native (storage v2) File implementation.

Design (see ``frappe/storage/SPEC.md``):

- A File row links to an immutable ``File Blob``; ``put_blob`` owns the
  best-effort dedup on ``(checksum, is_private, driver)``.
- Every byte access goes through the storage driver.
- ``file_url`` derives from the blob: ``/files/<blob>/<filename>`` or
  ``/private/files/<blob>/<filename>``. A public local blob sits on disk
  at that path, so nginx serves it.
- A privacy flip re-puts the bytes into the other namespace and repoints
  the row; bytes are never moved or rewritten in place.
- Deleting a File row never deletes bytes synchronously. Garbage
  collection (``frappe.storage.gc``) owns the bytes of orphan blobs.

Compat shim: a site can enable ``storage_v2`` while legacy rows are
still unbackfilled (``blob`` is NULL). Those rows are read through
``FileV1``'s disk path — reads only. The shim is deleted together with
``file_v1.py`` once the backfill is mandatory.
"""

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
		self.flags.new_file = True
		frappe.db.after_rollback.add(self.on_rollback)

	def _store_content(self, ignore_existing_file_check=False, overwrite=False):
		"""Write ``self._content`` through the active driver.

		``put_blob`` dedups on content, so ``ignore_existing_file_check``
		and ``overwrite`` have no meaning here."""
		from frappe.storage.blob import validate_upload

		if isinstance(self._content, str):
			self._content = self._content.encode()
		self.check_content()
		blob = frappe.storage.put_blob(
			io.BytesIO(self._content),
			is_private=bool(self.is_private),
			filename=self.file_name,
		)
		# reject active content hidden under a mismatched extension on the
		# standard write path too, not only in finish_upload
		validate_upload(blob, self.file_name)
		self.blob = blob.name
		self.flags.stored_blob = blob.name
		self.file_size = blob.file_size
		self.set_blob_file_url(blob)
		return {"file_name": self.file_name, "file_url": self.file_url}

	def on_rollback(self):
		# Nothing to undo: blobs are immutable, and a blob whose File row
		# was rolled back is an orphan that garbage collection sweeps.
		self.flags.pop("new_file", None)

	def before_save(self):
		super().before_save()
		self.enforce_blob_privacy()

	def enforce_blob_privacy(self):
		"""Point a blob-backed File at a blob in its own privacy namespace.

		A File subclass may override validate() without calling super()
		for existing rows (Drive's override does), so this runs from
		before_save."""
		if self.is_folder or self.is_new() or not self.get("blob"):
			return
		blob_is_private = frappe.db.get_value("File Blob", self.blob, "is_private")
		if blob_is_private is None or cint(blob_is_private) == cint(self.is_private):
			return
		old_file_url = self.file_url
		self.flip_blob_privacy()
		self.update_attached_to_field(old_file_url)

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

		old_file_url = self.file_url
		self.flip_blob_privacy()
		self.update_attached_to_field(old_file_url)

	def flip_blob_privacy(self):
		"""Re-put the bytes into the other privacy namespace and repoint.

		Blobs are immutable, so a privacy change never moves bytes in
		place. The old blob is left for garbage collection. An unbackfilled
		legacy row is adopted into blob storage by the same move; its old
		disk file stays behind for other rows that share the URL."""
		with self._open_stored_bytes() as stream:
			new_blob = frappe.storage.put_blob(
				stream,
				is_private=bool(cint(self.is_private)),
				filename=self.file_name,
			)
		self.blob = new_blob.name
		self.flags.stored_blob = new_blob.name
		self.set_blob_file_url(new_blob)

	def adopt_blob_from_file_url(self):
		"""Set ``blob`` from the blob behind file_url.

		Rows rebuilt from a bare file_url (amend of a submittable doc,
		attachment copies) reference an existing blob; no bytes to write.
		The URL is a blob URL, or a v1 URL whose bytes moved into a blob,
		which keeps its v1 URL. A private blob is adopted only when the
		user can already download it, so knowing a URL does not grant
		access to the file."""
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
		"""Never delete bytes synchronously; garbage collection owns them."""


def create_file_from_blob(
	blob,
	file_name: str,
	*,
	attached_to_doctype: str | None = None,
	attached_to_name: str | None = None,
	attached_to_field: str | None = None,
	is_private: bool = False,
	ignore_permissions: bool = False,
) -> "File":
	"""Create a File row for an existing Ready blob without re-writing bytes.

	``blob`` is a File Blob doc or name. The row goes through the normal
	insert lifecycle (permissions, attachment limits, attachment comment),
	but skips save_file: the bytes are already stored."""
	if isinstance(blob, str):
		blob = frappe.get_doc("File Blob", blob)

	if blob.status != "Ready":
		frappe.throw(_("Blob {0} is not ready").format(blob.name))

	if cint(blob.is_private) != cint(is_private):
		frappe.throw(_("Blob {0} privacy does not match the requested file privacy").format(blob.name))

	file = frappe.new_doc("File")
	file.update(
		{
			"file_name": file_name,
			"is_private": cint(is_private),
			"attached_to_doctype": attached_to_doctype,
			"attached_to_name": attached_to_name,
			"attached_to_field": attached_to_field,
			"blob": blob.name,
			"file_size": blob.file_size,
		}
	)
	file.flags.from_existing_blob = True
	# the caller supplied these bytes, like a fresh upload
	file.flags.stored_blob = blob.name
	for hook in frappe.get_hooks("after_file_upload"):
		# hook paths come from installed apps' hooks.py, as in frappe.handler.upload_file
		# nosemgrep: frappe-semgrep-rules.rules.security.frappe-codeinjection-eval
		file = frappe.call(hook, doc=file)
	file.insert(ignore_permissions=ignore_permissions)
	if not file.flags.attachment_record_created and not file.is_folder:
		# a File subclass may override after_insert() without calling
		# super(); keep attachment-comment parity with the upload path
		file.create_attachment_record()
	return file
