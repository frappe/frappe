# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Legacy (storage v1) File implementation.

Bytes live directly under ``public/files`` and ``private/files``, dedup
rides on ``content_hash``, privacy flips move files on disk, and the
``write_file`` / ``delete_file_data_content`` hooks may replace the byte
handling. All bodies are moved verbatim from the pre-storage-v2
``file.py``.

Compat shim: turning ``storage_v2`` off must stay safe on a site that
already has blob-backed rows (the flag is the documented rollback lever).
Rows with ``blob`` set are handled through ``FileV2``'s methods, the
mirror image of ``FileV2``'s shim for unbackfilled legacy rows. The
imports are lazy because ``file_v2`` imports this module at load time.

This whole file is deleted when storage v1 is removed.
"""

import os
import shutil

import frappe
from frappe import _
from frappe.utils import (
	call_hook_method,
	cint,
	get_files_path,
	get_hook_method,
	get_url,
)
from frappe.utils.file_manager import is_safe_path

from .file import URL_PREFIXES, File
from .utils import (
	delete_file,
	generate_file_name,
	get_content_hash,
	get_safe_file_name,
	update_existing_file_docs,
)


class FileV1(File):
	def _ingest_new_content(self):
		if not self.get("blob") and not self.content and self.file_url and self.file_url.startswith("/f/"):
			# compat shim: a copied row (amend, attachment copy) made under
			# storage v2 carries only a /f/ file_url; relink the blob
			self.adopt_blob_from_file_url()

		if self.flags.from_existing_blob:
			# compat shim: the row points at an already stored blob
			self.set_blob_file_url()
			return

		if self.is_remote_file:
			self.validate_remote_file()
		else:
			self.save_file(content=self.get_content())
			self.flags.new_file = True
			frappe.db.after_rollback.add(self.on_rollback)

		if not self.get("blob"):
			# blob rows dedup inside put_blob; the disk-based duplicate check does not apply
			self.validate_duplicate_entry()  # Hash is generated in save_file

	def on_rollback(self):
		rollback_flags = ("new_file", "original_content", "original_path")

		def pop_rollback_flags():
			for flag in rollback_flags:
				self.flags.pop(flag, None)

		# following condition is only executed when an insert has been rolledback
		if self.flags.new_file:
			self._delete_file_on_disk()
			pop_rollback_flags()
			return

		# if original_content flag is set, this rollback should revert the file to its original state
		if self.flags.original_content:
			file_path = self.get_full_path()

			if isinstance(self.flags.original_content, bytes):
				mode = "wb+"
			elif isinstance(self.flags.original_content, str):
				mode = "w+"

			with open(file_path, mode) as f:
				f.write(self.flags.original_content)
				os.fsync(f.fileno())
				pop_rollback_flags()

		# used in case file path (File.file_url) has been changed
		if self.flags.original_path:
			target = self.flags.original_path["old"]
			source = self.flags.original_path["new"]
			shutil.move(source, target)
			pop_rollback_flags()

	def before_save(self):
		if self.get("blob"):
			# compat shim: re-assert the blob privacy invariant for
			# subclasses that override validate() without calling super()
			from .file_v2 import FileV2

			FileV2.before_save(self)

	def validate_file_path(self):
		if self.is_remote_file:
			return

		if self.get("blob"):
			# compat shim: the path derives from the blob key
			return

		base_path = os.path.realpath(get_files_path(is_private=self.is_private))
		if not os.path.realpath(self.get_full_path()).startswith(base_path):
			frappe.throw(
				_("The File URL you've entered is incorrect"),
				title=_("Invalid File URL"),
			)

	def validate_file_url(self):
		if self.is_remote_file or not self.file_url:
			return

		if self.get("blob"):
			from .file_v2 import FileV2

			return FileV2.validate_file_url(self)  # compat shim: blob-backed row

		if not self.file_url.startswith(("/files/", "/private/files/")):
			# Probably an invalid URL since it doesn't start with http either
			frappe.throw(
				_("URL must start with http:// or https://"),
				title=_("Invalid URL"),
			)

	def handle_is_private_changed(self):
		if self.is_remote_file:
			return

		if self.get("blob"):
			# compat shim: blobs are immutable; repoint instead of moving bytes
			from .file_v2 import FileV2

			return FileV2.handle_is_private_changed(self)

		from pathlib import Path

		old_file_url = self.file_url
		file_name = self.file_url.split("/")[-1]
		private_file_path = Path(frappe.get_site_path("private", "files", file_name))
		public_file_path = Path(frappe.get_site_path("public", "files", file_name))

		if cint(self.is_private):
			source = public_file_path
			target = private_file_path
			url_starts_with = "/private/files/"
		else:
			source = private_file_path
			target = public_file_path
			url_starts_with = "/files/"
		updated_file_url = f"{url_starts_with}{file_name}"

		# if a file document is created by passing dict throught get_doc and __local is not set,
		# handle_is_private_changed would be executed; we're checking if updated_file_url is same
		# as old_file_url to avoid a FileNotFoundError for this case.
		if updated_file_url == old_file_url:
			return

		if not source.exists():
			frappe.throw(
				_("Cannot find file {} on disk").format(source),
				exc=FileNotFoundError,
			)
		if target.exists():
			frappe.throw(
				_("A file with same name {} already exists").format(target),
				exc=FileExistsError,
			)

		# Uses os.rename which is an atomic operation
		shutil.move(source, target)
		self.flags.original_path = {"old": source, "new": target}
		frappe.db.after_rollback.add(self.on_rollback)

		self.file_url = updated_file_url
		update_existing_file_docs(self)
		self.update_attached_to_field(old_file_url)

	def validate_file_on_disk(self):
		"""Validates existence file"""
		if self.get("blob"):
			from .file_v2 import FileV2

			return FileV2.validate_file_on_disk(self)  # compat shim: blob-backed row

		full_path = self.get_full_path()

		if full_path.startswith(URL_PREFIXES):
			return True

		if not os.path.exists(full_path):
			frappe.throw(_("File {0} does not exist").format(self.file_url), IOError)

	def validate_duplicate_entry(self):
		if not self.flags.ignore_duplicate_entry_error and not self.is_folder:
			if not self.content_hash:
				self.generate_content_hash()

			# check duplicate name
			# check duplicate assignment
			filters = {
				"content_hash": self.content_hash,
				"is_private": self.is_private,
			}

			if self.name:
				filters.update({"name": ("!=", self.name)})

			if self.attached_to_doctype and self.attached_to_name:
				filters.update(
					{
						"attached_to_doctype": self.attached_to_doctype,
						"attached_to_name": self.attached_to_name,
					}
				)
			duplicate_file = frappe.db.get_value("File", filters, ["name", "file_url"], as_dict=1)

			if duplicate_file:
				duplicate_file_doc = frappe.get_cached_doc("File", duplicate_file.name)
				if duplicate_file_doc.exists_on_disk():
					# just use the url, to avoid uploading a duplicate
					self.file_url = duplicate_file.file_url

	def generate_content_hash(self):
		if self.content_hash or not self.file_url or self.is_remote_file:
			return
		file_name = self.file_url.split("/")[-1]
		try:
			file_path = get_files_path(file_name, is_private=self.is_private)
			with open(file_path, "rb") as f:
				self.content_hash = get_content_hash(f.read())
		except OSError:
			frappe.throw(_("File {0} does not exist").format(file_path))

	def _delete_file_on_disk(self):
		"""If file not attached to any other record, delete it"""
		if self.get("blob"):
			# compat shim: garbage collection owns blob bytes and thumbnails;
			# deleting a File row never deletes them synchronously
			return

		on_disk_file_not_shared = self.content_hash and not frappe.get_all(
			"File",
			filters={
				"content_hash": self.content_hash,
				"name": ["!=", self.name],
				# NOTE: Some old Files might share file_urls while not sharing the is_private value
				# "is_private": self.is_private,
			},
			limit=1,
		)
		if on_disk_file_not_shared:
			self.delete_file_data_content()
		else:
			self.delete_file_data_content(only_thumbnail=True)

	def exists_on_disk(self):
		if self.get("blob"):
			from .file_v2 import FileV2

			return FileV2.exists_on_disk(self)  # compat shim: blob-backed row

		return os.path.exists(self.get_full_path())

	def _read_content(self) -> bytes:
		if self.get("blob"):
			from .file_v2 import FileV2

			return FileV2._read_content(self)  # compat shim: blob-backed row

		if self.file_url:
			self.validate_file_url()
		file_path = self.get_full_path()

		with open(file_path, mode="rb") as f:
			return f.read()

	def get_full_path(self):
		"""Return file path using the set file name."""

		if self.get("blob"):
			from .file_v2 import FileV2

			return FileV2.get_full_path(self)  # compat shim: blob-backed row

		file_path = self.file_url or self.file_name

		site_url = get_url()
		if "/files/" in file_path and file_path.startswith(site_url):
			file_path = file_path.split(site_url, 1)[1]

		if "/" not in file_path:
			if self.is_private:
				file_path = f"/private/files/{file_path}"
			else:
				file_path = f"/files/{file_path}"

		if file_path.startswith("/private/files/"):
			file_path = get_files_path(*file_path.split("/private/files/", 1)[1].split("/"), is_private=1)

		elif file_path.startswith("/files/"):
			file_path = get_files_path(*file_path.split("/files/", 1)[1].split("/"))

		elif file_path.startswith(URL_PREFIXES):
			pass

		elif not self.file_url:
			frappe.throw(_("There is some problem with the file url: {0}").format(file_path))

		if not is_safe_path(file_path):
			frappe.throw(_("Cannot access file path {0}").format(file_path))

		if os.path.sep in self.file_name:
			frappe.throw(_("File name cannot have {0}").format(os.path.sep))

		return file_path

	def write_file(self):
		"""write file to disk with a random name (to compare)"""
		if self.is_remote_file:
			return

		file_path = self.get_full_path()

		if isinstance(self._content, str):
			self._content = self._content.encode()
		self.check_content()
		with open(file_path, "wb+") as f:
			f.write(self._content)
			os.fsync(f.fileno())

		frappe.db.after_rollback.add(self.on_rollback)

		return file_path

	def _stash_original_content(self):
		# blob-backed rows have no in-place write to roll back (compat shim)
		if not self.flags.new_file and not self.get("blob"):
			self.flags.original_content = self.get_content()

	def _store_content(self, ignore_existing_file_check=False, overwrite=False):
		file_exists = False
		duplicate_file = None

		# check if a file exists with the same content hash and is also in the same folder (public or private)
		if not ignore_existing_file_check:
			duplicate_file = frappe.get_value(
				"File",
				{"content_hash": self.content_hash, "is_private": self.is_private},
				["file_url", "name"],
				as_dict=True,
			)

		if duplicate_file:
			file_doc: File = frappe.get_cached_doc("File", duplicate_file.name)
			if file_doc.exists_on_disk():
				if self.exists_on_disk():
					if not self.file_url:
						self.file_url = duplicate_file.file_url
				else:
					self.file_url = duplicate_file.file_url
				file_exists = True

		if not file_exists:
			if not overwrite:
				self.file_name = generate_file_name(
					name=self.file_name,
					suffix=self.content_hash[-6:],
					is_private=self.is_private,
					content_hash=self.content_hash,
				)
			call_hook_method("before_write_file", file_size=self.file_size)
			write_file_method = get_hook_method("write_file")
			if write_file_method:
				return write_file_method(self)
			return self.save_file_on_filesystem()

	def save_file_on_filesystem(self):
		safe_file_name = get_safe_file_name(self.file_name)
		if self.is_private:
			self.file_url = f"/private/files/{safe_file_name}"
		else:
			self.file_url = f"/files/{safe_file_name}"

		fpath = self.write_file()

		return {"file_name": os.path.basename(fpath), "file_url": self.file_url}

	def delete_file_data_content(self, only_thumbnail=False):
		method = get_hook_method("delete_file_data_content")
		if method:
			method(self, only_thumbnail=only_thumbnail)
		else:
			self.delete_file_from_filesystem(only_thumbnail=only_thumbnail)

	def delete_file_from_filesystem(self, only_thumbnail=False):
		"""Delete file, thumbnail from File document"""
		if only_thumbnail:
			delete_file(self.thumbnail_url)
		else:
			delete_file(self.file_url)
			delete_file(self.thumbnail_url)

	# --- compat shim: v2 helper methods, so FileV2 bodies invoked on
	# blob-backed rows resolve their internal self.* calls on a FileV1
	# instance. Lazy imports: file_v2 imports this module at load time. ---

	def adopt_blob_from_file_url(self):
		from .file_v2 import FileV2

		return FileV2.adopt_blob_from_file_url(self)

	def set_blob_file_url(self, blob=None):
		from .file_v2 import FileV2

		return FileV2.set_blob_file_url(self, blob)

	def flip_blob_privacy(self):
		from .file_v2 import FileV2

		return FileV2.flip_blob_privacy(self)

	def _open_stored_bytes(self):
		from .file_v2 import FileV2

		return FileV2._open_stored_bytes(self)
