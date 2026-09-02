# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Storage-agnostic ``File`` base class.

``File`` owns everything that does not depend on where the bytes live:
naming, the folder tree, attachment links and their validation,
permissions, attachment comments and shared orchestration (content
preparation, exif stripping, size checks, optimize/thumbnail flows).

The byte handling lives in one of two concrete classes:

- ``FileV1`` (``file_v1.py``): the legacy disk layout. Deleted when
  storage v1 is removed.
- ``FileV2`` (``file_v2.py``): blob-native storage through
  ``frappe.storage``.

``resolve_controller`` picks the concrete class per site, based on the
``storage_v2`` site config flag. The result is cached by
``frappe.get_controller``, so every ``frappe.get_doc("File", ...)``
returns the right implementation and ``isinstance(doc, File)`` holds for
both.
"""

import copyreg
import io
import mimetypes
import os
import re
import zipfile
from urllib.parse import quote, unquote

import filetype
from PIL import Image, ImageFile, ImageOps

import frappe
from frappe import _
from frappe.database.schema import SPECIAL_CHAR_PATTERN
from frappe.exceptions import DoesNotExistError
from frappe.model.document import Document
from frappe.permissions import SYSTEM_USER_ROLE, get_doctypes_with_read
from frappe.utils import (
	cint,
	get_url,
)
from frappe.utils.html_utils import escape_html
from frappe.utils.image import optimize_image, strip_exif_data
from frappe.utils.pdf import pdf_contains_js

from .exceptions import (
	AttachmentLimitReached,
	FileTypeNotAllowed,
	FolderNotEmpty,
	MaxFileSizeReachedError,
)
from .utils import *

exclude_from_linked_with = True

ImageFile.LOAD_TRUNCATED_IMAGES = True  # nosemgrep

URL_PREFIXES = ("http://", "https://", "/api/method/")
FILE_ENCODING_OPTIONS = ("utf-8-sig", "utf-8", "windows-1250", "windows-1252")
# OLE2 Compound File Binary signature, used by legacy .xls/.doc/.ppt files, which filetype fails to detect
OLE_FILE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class _ResolvedFileMeta(type(Document)):
	"""Metaclass of the spliced classes built by ``File.resolve_controller``.

	A spliced class is created at runtime, so it has no importable home.
	The ``copyreg`` registration below makes it pickle (document cache,
	background jobs) as "the class this site resolves File to"."""


def _restore_resolved_file_class(doctype):
	from frappe.model.base_document import get_controller

	return get_controller(doctype)


copyreg.pickle(_ResolvedFileMeta, lambda cls: (_restore_resolved_file_class, (cls._DOCTYPE_NAME,)))


class File(Document):
	_DOCTYPE_NAME = "File"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		attached_to_doctype: DF.Link | None
		attached_to_field: DF.Data | None
		attached_to_name: DF.Data | None
		blob: DF.Link | None
		content_hash: DF.Data | None
		file_name: DF.Data | None
		file_size: DF.Int
		file_type: DF.Data | None
		file_url: DF.Code | None
		folder: DF.Link | None
		is_attachments_folder: DF.Check
		is_folder: DF.Check
		is_home_folder: DF.Check
		is_private: DF.Check
		old_parent: DF.Data | None
		thumbnail_url: DF.SmallText | None
		uploaded_to_dropbox: DF.Check
		uploaded_to_google_drive: DF.Check
	# end: auto-generated types

	no_feed_on_delete = True

	@classmethod
	def resolve_controller(cls) -> type["File"]:
		"""Pick the storage implementation for this site.

		Called once per site by ``import_controller``; ``get_controller``
		caches the result. An app that replaces File through
		``override_doctype_class`` keeps its class on top: the site's
		storage implementation is spliced in under it, so the override's
		method resolution order stays override -> storage -> File."""
		import frappe.storage

		from .file_v1 import FileV1
		from .file_v2 import FileV2

		if issubclass(cls, FileV1 | FileV2):
			return cls

		concrete = FileV2 if frappe.storage.enabled() else FileV1
		if cls is File:
			return concrete

		return _ResolvedFileMeta(cls.__name__, (cls, concrete), {"__module__": cls.__module__})

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		# if content is set, file_url will be generated
		# decode comes in the picture if content passed has to be decoded before writing to disk

		self.content = self.get("content") or b""
		self.decode = self.get("decode", False)

	@property
	def is_remote_file(self):
		if self.file_url:
			return self.file_url.startswith(URL_PREFIXES)
		return not self.content

	def autoname(self):
		"""Set name for folder"""
		if self.is_folder:
			if self.folder:
				self.name = self.get_name_based_on_parent_folder()
			else:
				# home
				self.name = self.file_name
		else:
			self.name = frappe.generate_hash(length=10)

	def before_insert(self):
		if self.attached_to_doctype and not self.attached_to_name:
			self.attached_to_doctype = None
			self.attached_to_field = None
		# Ensure correct formatting and type
		self.file_url = unquote(self.file_url) if self.file_url else ""

		self.set_folder_name()
		self.set_is_private()
		self.set_file_name()
		self.validate_attachment_limit()
		self.set_file_type()
		self.validate_file_extension()
		self.validate_private_file_access()

		if self.is_folder:
			return

		if self.flags.copy_from_existing_file:
			# Preserve the normal insert lifecycle for hooks and validations, but skip
			# reprocessing an existing blob that is already referenced by `file_url`.
			if not self.file_url:
				frappe.throw(
					_("File URL is required when copying an existing attachment."),
					exc=frappe.MandatoryError,
				)
			return

		self._ingest_new_content()

	def after_insert(self):
		if not self.is_folder:
			self.create_attachment_record()

	def create_attachment_copy(
		self,
		attached_to_doctype: str,
		attached_to_name: str,
		attached_to_field: str | None = None,
		ignore_permissions: bool = False,
	):
		"""Efficiently copy an attachment from one document to another by reusing `file_url`."""
		if self.is_folder:
			frappe.throw(_("Cannot attach a folder to a document"))

		attachment = frappe.copy_doc(self)
		attachment.update(
			{
				"attached_to_doctype": attached_to_doctype,
				"attached_to_name": attached_to_name,
				"attached_to_field": attached_to_field,
			}
		)
		attachment.folder = None
		attachment.flags.copy_from_existing_file = True
		return attachment.insert(ignore_permissions=ignore_permissions)

	def validate(self):
		if self.is_folder:
			return

		self.validate_attachment_references()
		self.enforce_public_file_restrictions()

		# when dict is passed to get_doc for creation of new_doc, is_new returns None
		# this case is handled inside handle_is_private_changed
		if not self.is_new() and self.has_value_changed("is_private"):
			self.handle_is_private_changed()

		self.validate_file_path()
		self.validate_file_url()
		self.validate_file_on_disk()
		self.file_size = frappe.form_dict.file_size or self.file_size

	def validate_attachment_references(self):
		if not self.attached_to_doctype:
			return

		if not self.attached_to_name or not isinstance(self.attached_to_name, str | int):
			frappe.throw(
				_("Attached To Name must be a string or an integer"),
				frappe.ValidationError,
			)

		if self.attached_to_field and SPECIAL_CHAR_PATTERN.search(self.attached_to_field):
			frappe.throw(_("The fieldname you've specified in Attached To Field is invalid"))

	def enforce_public_file_restrictions(self):
		if not self.is_private and frappe.get_system_settings(
			"only_allow_system_managers_to_upload_public_files"
		):
			try:
				frappe.only_for("System Manager")
			except PermissionError:
				frappe.throw(_("Only System Managers can make this file public."))

	def validate_private_file_access(self):
		"""Validate that the user has permission to access an existing private file."""
		if not self.file_url:
			return

		existing_files = frappe.get_all(
			"File",
			filters={"file_url": self.file_url},
			fields=["name", "owner", "is_private"],
			limit=1,
		)

		if not existing_files:
			return

		existing_file = existing_files[0]

		if existing_file.is_private:
			user = frappe.session.user

			if user == existing_file.owner or user == "Administrator":
				return

			existing_doc = frappe.get_doc("File", existing_file.name)
			if not has_permission(existing_doc, "read", user=user):
				frappe.throw(
					_("You do not have permission to access this file"),
					frappe.PermissionError,
				)

	def after_rename(self, *args, **kwargs):
		for successor in self.get_successors():
			setup_folder_path(successor, self.name)

	def on_trash(self):
		if self.is_home_folder or self.is_attachments_folder:
			frappe.throw(_("Cannot delete Home and Attachments folders"))
		self.validate_empty_folder()
		self.validate_protected_file()
		self.validate_not_referenced_in_attach_field()
		self._delete_file_on_disk()
		if not self.is_folder:
			self.add_comment_in_reference_doc("Attachment Removed", self.file_name)

	def get_name_based_on_parent_folder(self) -> str | None:
		if self.folder:
			return os.path.join(self.folder, self.file_name)

	def get_successors(self):
		return frappe.get_all("File", filters={"folder": self.name}, pluck="name")

	def update_attached_to_field(self, old_file_url):
		if (
			not self.attached_to_doctype
			or not self.attached_to_name
			or not self.fetch_attached_to_field(old_file_url)
		):
			return

		if frappe.get_meta(self.attached_to_doctype).issingle:
			frappe.db.set_single_value(
				self.attached_to_doctype,
				self.attached_to_field,
				self.file_url,
			)
		else:
			frappe.db.set_value(
				self.attached_to_doctype,
				self.attached_to_name,
				self.attached_to_field,
				self.file_url,
			)

	def fetch_attached_to_field(self, old_file_url):
		if self.attached_to_field:
			return True

		reference_dict = frappe.get_doc(self.attached_to_doctype, self.attached_to_name).as_dict()

		for key, value in reference_dict.items():
			if value == old_file_url:
				self.attached_to_field = key
				return True

	def validate_attachment_limit(self):
		attachment_limit = 0
		if self.attached_to_doctype and self.attached_to_name:
			attachment_limit = cint(frappe.get_meta(self.attached_to_doctype).max_attachments)

		if attachment_limit:
			current_attachment_count = len(
				frappe.get_all(
					"File",
					filters={
						"attached_to_doctype": self.attached_to_doctype,
						"attached_to_name": self.attached_to_name,
					},
					limit=attachment_limit + 1,
				)
			)

			if current_attachment_count >= attachment_limit:
				frappe.throw(
					_("Maximum Attachment Limit of {0} has been reached for {1} {2}.").format(
						frappe.bold(attachment_limit),
						self.attached_to_doctype,
						self.attached_to_name,
					),
					exc=AttachmentLimitReached,
					title=_("Attachment Limit Reached"),
				)

	def validate_remote_file(self):
		"""Validates if file uploaded using URL already exist"""
		site_url = get_url()
		if self.file_url and "/files/" in self.file_url and self.file_url.startswith(site_url):
			self.file_url = self.file_url.split(site_url, 1)[1]

	def set_folder_name(self):
		"""Make parent folders if not exists based on reference doctype and name"""
		if self.folder:
			return

		if self.attached_to_doctype:
			self.folder = frappe.db.get_value("File", {"is_attachments_folder": 1})

		elif not self.is_home_folder:
			self.folder = "Home"

	def set_file_type(self):
		if self.is_folder:
			return

		file_type = mimetypes.guess_type(self.file_name)[0]
		if not file_type:
			return

		file_extension = mimetypes.guess_extension(file_type)
		self.file_type = file_extension.lstrip(".").upper() if file_extension else None

	def validate_file_extension(self):
		# Only validate uploaded files, not generated by code/integrations.
		if not self.file_type or not frappe.request:
			return

		allowed_extensions = frappe.get_system_settings("allowed_file_extensions")
		if not allowed_extensions:
			return

		if self.file_type not in allowed_extensions.splitlines():
			frappe.throw(
				_("File type of {0} is not allowed").format(self.file_type),
				exc=FileTypeNotAllowed,
			)

	def check_content(self):
		if self.file_type == "PDF" and self._content and pdf_contains_js(self._content):
			frappe.throw(_("This PDF cannot be uploaded as it contains unsafe content."))

	def set_file_name(self):
		if not self.file_name and not self.file_url:
			frappe.throw(
				_("Fields `file_name` or `file_url` must be set for File"),
				exc=frappe.MandatoryError,
			)
		elif not self.file_name and self.file_url:
			self.file_name = self.file_url.split("/")[-1]
		else:
			self.file_name = re.sub(r"/", "", self.file_name)

	def make_thumbnail(
		self,
		set_as_thumbnail: bool = True,
		width: int = 300,
		height: int = 300,
		suffix: str = "small",
		crop: bool = False,
	) -> str:
		from requests.exceptions import HTTPError, SSLError

		if not self.file_url:
			return

		try:
			if self.file_url.startswith(("/files", "/private/files")):
				image, filename, extn = get_local_image(self.file_url)
			else:
				image, filename, extn = get_web_image(self.file_url)
		except (HTTPError, SSLError, OSError, TypeError):
			return

		size = width, height
		if crop:
			image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)
		else:
			image.thumbnail(size, Image.Resampling.LANCZOS)

		thumbnail_url = f"{filename}_{suffix}.{extn}"
		path = os.path.abspath(frappe.get_site_path("public", thumbnail_url.lstrip("/")))

		try:
			image.save(path)
			if set_as_thumbnail:
				self.db_set("thumbnail_url", thumbnail_url)

		except OSError:
			frappe.msgprint(_("Unable to write file format for {0}").format(path))
			return

		return thumbnail_url

	def validate_empty_folder(self):
		"""Throw exception if folder is not empty"""
		if self.is_folder and frappe.get_all("File", filters={"folder": self.name}, limit=1):
			frappe.throw(_("Folder {0} is not empty").format(self.name), FolderNotEmpty)

	def validate_protected_file(self):
		"""Throw an exception if this file is attached to a doctype that protects files.

		Allows deleting the attached file if the linked document is in draft. If submitted,
		deletion is not allowed. If canceled, requires delete permissions on the linked document.
		"""
		if not (self.attached_to_doctype and self.attached_to_name):
			return

		try:
			ref_doc = frappe.get_doc(self.attached_to_doctype, self.attached_to_name)
		except DoesNotExistError:
			return

		if ref_doc.docstatus == 0:
			# If the document is not submitted yet, users can correct wrong attachments
			return

		if not ref_doc.meta.protect_attached_files:
			return

		if ref_doc.docstatus == 2 and ref_doc.has_permission("delete"):
			# Deletion must still be possible if users have the permission to delete the linked document
			return

		frappe.throw(
			msg=_("This file is attached to a protected document and cannot be deleted."),
			title=_("Protected File"),
		)

	def validate_not_referenced_in_attach_field(self):
		"""Throw an exception if the linked document still has this file's URL set in an Attach field."""
		if self.flags.force_delete:
			return

		if not (self.attached_to_doctype and self.attached_to_name and self.file_url):
			return

		url_backed_by_another_file = frappe.get_all(
			"File",
			filters={"file_url": self.file_url, "name": ["!=", self.name]},
			limit=1,
		)
		if url_backed_by_another_file:
			return

		try:
			ref_doc = frappe.get_doc(self.attached_to_doctype, self.attached_to_name)
		except DoesNotExistError:
			return

		def get_referencing_field(doc):
			for df in doc.meta.get("fields", {"fieldtype": ["in", ["Attach", "Attach Image"]]}):
				if doc.get(df.fieldname) == self.file_url:
					return df

		docs_to_check = [ref_doc]
		for table_field in ref_doc.meta.get_table_fields():
			docs_to_check.extend(ref_doc.get(table_field.fieldname))

		referencing_field = None
		referencing_doc = None
		for doc in docs_to_check:
			if referencing_field := get_referencing_field(doc):
				referencing_doc = doc
				break

		if not referencing_field:
			return

		if ref_doc.docstatus > 0 and not referencing_field.allow_on_submit:
			return

		field_label = frappe.bold(_(referencing_field.label or referencing_field.fieldname))

		if referencing_doc is ref_doc:
			msg = _(
				"This file cannot be deleted as it is set in field {0} of {1} {2}. Clear the field first."
			).format(field_label, _(ref_doc.doctype), ref_doc.name)
		else:
			msg = _(
				"This file cannot be deleted as it is set in field {0} in row {1} of {2} {3}. Clear the field first."
			).format(field_label, referencing_doc.idx, _(ref_doc.doctype), ref_doc.name)

		frappe.throw(msg, frappe.LinkExistsError)

	def unzip(self) -> list["File"]:
		"""Unzip current file and replace it by its children"""
		from frappe.core.api.file import get_max_extract_size

		if not self.file_url.endswith(".zip"):
			frappe.throw(_("{0} is not a zip file").format(self.file_name))

		zip_path = self.get_full_path()
		max_extracted_size = get_max_extract_size()

		files = []
		total_extracted_size = 0
		with zipfile.ZipFile(zip_path) as z:
			# skip directories, macos hidden directory & hidden files
			members = [
				file
				for file in z.filelist
				if not (file.is_dir() or file.filename.startswith("__MACOSX/"))
				and not os.path.basename(file.filename).startswith(".")
			]

			# Reject on declared (central directory) sizes before reading any member,
			# so a small, highly compressible archive can't force large reads/writes.
			declared_total_size = sum(file.file_size for file in members)
			if declared_total_size > max_extracted_size:
				frappe.throw(
					_("Zip file extracts to more than the maximum allowed size of {0} MB").format(
						max_extracted_size // 1048576
					)
				)

			try:
				for file in members:
					filename = os.path.basename(file.filename)

					file_doc = frappe.new_doc("File")
					try:
						content = z.read(file.filename)
					except zipfile.BadZipFile:
						frappe.throw(_("{0} is a not a valid zip file").format(self.file_name))

					total_extracted_size += len(content)
					if total_extracted_size > max_extracted_size:
						frappe.throw(
							_("Zip file extracts to more than the maximum allowed size of {0} MB").format(
								max_extracted_size // 1048576
							)
						)

					file_doc.content = content
					file_doc.file_name = filename
					file_doc.folder = self.folder
					file_doc.is_private = self.is_private
					file_doc.attached_to_doctype = self.attached_to_doctype
					file_doc.attached_to_name = self.attached_to_name
					file_doc.save()
					files.append(file_doc)
			except Exception:
				# roll back any children already persisted before the failure
				for file_doc in files:
					frappe.delete_doc("File", file_doc.name, ignore_permissions=True, force=True)
				raise

		frappe.delete_doc("File", self.name)
		return files

	def get_content(self, encodings=None) -> bytes | str:
		if self.is_folder:
			frappe.throw(_("Cannot get file contents of a Folder"))

		self.validate_file_path()
		# if doc was just created, content field is already populated, return it as-is
		if self.get("content"):
			self._content = self.content
			if self.decode:
				self._content = decode_file_content(self._content)
				self.decode = False
			# self.content = None # TODO: This needs to happen; make it happen somehow
			return self._content

		self._content = self._read_content()

		if encodings is None:
			encodings = FILE_ENCODING_OPTIONS
		# Only decode if not a binary file
		kind = filetype.guess(self._content)
		if not kind and not self._content.startswith(OLE_FILE_SIGNATURE):
			# looping will not result in slowdown, as the content is usually utf-8 or utf-8-sig
			# encoded so the first iteration will be enough most of the time
			for encoding in encodings:
				try:
					# read file with proper encoding
					self._content = self._content.decode(encoding)
					break
				except UnicodeDecodeError:
					# for .png, .jpg, etc
					continue

		return self._content

	def save_file(
		self,
		content: bytes | str | None = None,
		decode=False,
		ignore_existing_file_check=False,
		overwrite=False,
	):
		if self.is_remote_file:
			return

		self._stash_original_content()

		if content:
			self.content = content
			self.decode = decode
			self.get_content()

		if not self._content:
			return

		self.is_private = cint(self.is_private)
		self.content_type = mimetypes.guess_type(self.file_name)[0]

		# transform file content based on site settings
		if (
			self.content_type
			and self.content_type == "image/jpeg"
			and frappe.get_system_settings("strip_exif_metadata_from_uploaded_images")
		):
			self._content = strip_exif_data(self._content, self.content_type)

		self.file_size = self.check_max_file_size()
		self.content_hash = get_content_hash(self._content)

		return self._store_content(
			ignore_existing_file_check=ignore_existing_file_check, overwrite=overwrite
		)

	def check_max_file_size(self):
		from frappe.core.api.file import get_max_file_size

		max_file_size = get_max_file_size()
		file_size = len(self._content or b"")

		if not self.flags.skip_file_size_check and file_size > max_file_size:
			msg = _("File size exceeded the maximum allowed size of {0} MB").format(max_file_size / 1048576)
			if frappe.has_permission("System Settings", "write"):
				msg += ".<br>" + _("You can increase the limit from System Settings.")
			frappe.throw(msg, exc=MaxFileSizeReachedError)

		return file_size

	def is_downloadable(self):
		return has_permission(self, "read")

	def get_extension(self):
		"""Split and return filename and extension for the set `file_name`."""
		return os.path.splitext(self.file_name)

	def create_attachment_record(self):
		self.flags.attachment_record_created = True
		icon = ' <i class="fa fa-lock text-warning"></i>' if self.is_private else ""
		file_url = quote(frappe.safe_encode(self.file_url), safe="/:") if self.file_url else self.file_name
		file_name = escape_html(self.file_name or self.file_url)

		self.add_comment_in_reference_doc(
			"Attachment",
			f"<a href='{file_url}' target='_blank'>{file_name}</a>{icon}",
		)

	def add_comment_in_reference_doc(self, comment_type, text):
		if self.attached_to_doctype and self.attached_to_name:
			try:
				doc = frappe.get_doc(self.attached_to_doctype, self.attached_to_name)
				doc.add_comment(comment_type, text)
			except frappe.DoesNotExistError:
				frappe.clear_messages()

	def set_is_private(self):
		if self.is_private:
			return

		if self.file_url:
			self.is_private = cint(self.file_url.startswith("/private"))

	@frappe.whitelist()
	def optimize_file(self):
		if self.is_folder:
			raise TypeError("Folders cannot be optimized")

		content_type = mimetypes.guess_type(self.file_name)[0]
		is_local_image = content_type.startswith("image/") and self.file_size > 0
		is_svg = content_type == "image/svg+xml"

		if not is_local_image:
			raise NotImplementedError("Only local image files can be optimized")

		if is_svg:
			raise TypeError("Optimization of SVG images is not supported")

		original_content = self.get_content()
		optimized_content = optimize_image(
			content=original_content,
			content_type=content_type,
		)

		if original_content == optimized_content:
			# optimization failed, don't resave it
			return

		self.save_file(content=optimized_content, overwrite=True)
		self.save()

	@property
	def unique_url(self) -> str:
		"""Unique URL contains file ID in URL to speed up permisison checks."""
		from urllib.parse import urlencode

		if self.is_private:
			return self.file_url + "?" + urlencode({"fid": self.name})
		else:
			return self.file_url

	@staticmethod
	def zip_files(files):
		zip_file = io.BytesIO()
		zf = zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED)
		for _file in files:
			if isinstance(_file, str):
				_file = frappe.get_doc("File", _file)
			if not isinstance(_file, File):
				continue
			if _file.is_folder:
				continue
			if not has_permission(_file, "read"):
				continue
			zf.writestr(_file.file_name, _file.get_content())
		zf.close()
		return zip_file.getvalue()

	# --- storage seams, implemented by FileV1 / FileV2 ---

	def _ingest_new_content(self):
		"""Store the incoming bytes (or validate the remote/blob reference) on insert."""
		self._storage_not_resolved()

	def _read_content(self) -> bytes:
		"""Return the stored bytes."""
		self._storage_not_resolved()

	def _store_content(self, ignore_existing_file_check=False, overwrite=False):
		"""Persist ``self._content`` and set ``file_url``."""
		self._storage_not_resolved()

	def _stash_original_content(self):
		"""Keep state needed to undo an in-place content update on rollback.

		Nothing to keep by default; only legacy storage rewrites bytes in
		place (``FileV1`` overrides this)."""

	def get_full_path(self):
		self._storage_not_resolved()

	def exists_on_disk(self):
		self._storage_not_resolved()

	def validate_file_path(self):
		self._storage_not_resolved()

	def validate_file_url(self):
		self._storage_not_resolved()

	def validate_file_on_disk(self):
		self._storage_not_resolved()

	def handle_is_private_changed(self):
		self._storage_not_resolved()

	def _delete_file_on_disk(self):
		self._storage_not_resolved()

	def _storage_not_resolved(self):
		raise NotImplementedError(
			f"{type(self).__name__} has no storage implementation. File controllers "
			"must be loaded through frappe.get_doc / frappe.get_controller so that "
			"File.resolve_controller can pick FileV1 or FileV2 for the site."
		)


def on_doctype_update():
	frappe.db.add_index("File", ["attached_to_doctype", "attached_to_name"])
	frappe.db.add_index("File", ["file_url(100)"])


def has_permission(doc, ptype=None, user=None, debug=False):
	user = user or frappe.session.user

	if any(frappe.get_hooks("ignore_file_permissions")):
		return True

	if user == "Administrator":
		return True

	if not doc.is_private and ptype in ("read", "select"):
		return True

	if user != "Guest" and doc.owner == user:
		return True
	if (
		user != "Guest"
		and ptype in ["read", "write", "share", "submit"]
		and frappe.share.get_shared(
			"File", filters=[["share_name", "=", doc.name]], rights=[ptype], user=user
		)
	):
		return True

	if doc.attached_to_doctype and doc.attached_to_name:
		attached_to_doctype = doc.attached_to_doctype
		attached_to_name = doc.attached_to_name

		try:
			ref_doc = frappe.get_lazy_doc(attached_to_doctype, attached_to_name)
		except (ModuleNotFoundError, ImportError):
			return False
		except frappe.DoesNotExistError:
			frappe.clear_last_message()
			return False

		if ptype in ["write", "create", "delete"]:
			return ref_doc.has_permission("write", debug=debug, user=user)
		else:
			return ref_doc.has_permission("read", debug=debug, user=user)

	return False


def get_permission_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user

	if any(frappe.get_hooks("ignore_file_permissions")):
		return ""

	if user == "Administrator":
		return ""

	if SYSTEM_USER_ROLE not in frappe.get_roles(user):
		return f""" `tabFile`.`owner` = {frappe.db.escape(user)} """

	readable_doctypes = ", ".join(repr(dt) for dt in get_doctypes_with_read())
	return f"""
		(`tabFile`.`is_private` = 0)
		OR (`tabFile`.`attached_to_doctype` IS NULL AND `tabFile`.`owner` = {frappe.db.escape(user)})
		OR (`tabFile`.`attached_to_doctype` IN ({readable_doctypes}))
	"""


# Note: kept at the end to not cause circular, partial imports & maintain backwards compatibility
from frappe.core.api.file import *
