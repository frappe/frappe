# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import io
import mimetypes
import os
import re
import shutil
import zipfile
from urllib.parse import quote, unquote

from PIL import Image, ImageFile, ImageOps
from requests.exceptions import HTTPError, SSLError

import frappe
from frappe import _
from frappe.database.schema import SPECIAL_CHAR_PATTERN
from frappe.model.document import Document
from frappe.permissions import get_doctypes_with_read
from frappe.utils import call_hook_method, cint, get_files_path, get_hook_method, get_url
from frappe.utils.file_manager import is_safe_path
from frappe.utils.image import optimize_image, strip_exif_data

from .exceptions import AttachmentLimitReached, FolderNotEmpty, MaxFileSizeReachedError
from .utils import *

exclude_from_linked_with = True
ImageFile.LOAD_TRUNCATED_IMAGES = True
URL_PREFIXES = ("http://", "https://")


class File(Document):
	no_feed_on_delete = True

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
		self.set_folder_name()
		self.set_file_name()
		self.validate_attachment_limit()

		if self.is_folder:
			return

		if self.is_remote_file:
			self.validate_remote_file()
		else:
			self.save_file(content=self.get_content())
			self.flags.new_file = True
			frappe.local.rollback_observers.append(self)

	def after_insert(self):
		if not self.is_folder:
			self.create_attachment_record()
		self.set_is_private()
		self.set_file_name()
		self.validate_duplicate_entry()

	def validate(self):
		if self.is_folder:
			return

		# Ensure correct formatting and type
		self.file_url = unquote(self.file_url) if self.file_url else ""

		self.validate_attachment_references()

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

		if not self.attached_to_name or not isinstance(self.attached_to_name, (str, int)):
			frappe.throw(_("Attached To Name must be a string or an integer"), frappe.ValidationError)

		if self.attached_to_field and SPECIAL_CHAR_PATTERN.search(self.attached_to_field):
			frappe.throw(_("The fieldname you've specified in Attached To Field is invalid"))

	def after_rename(self, *args, **kwargs):
		for successor in self.get_successors():
			setup_folder_path(successor, self.name)

	def on_trash(self):
		if self.is_home_folder or self.is_attachments_folder:
			frappe.throw(_("Cannot delete Home and Attachments folders"))
		self.validate_empty_folder()
		self._delete_file_on_disk()
		if not self.is_folder:
			self.add_comment_in_reference_doc("Attachment Removed", _("Removed {0}").format(self.file_name))

	def on_rollback(self):
		# following condition is only executed when an insert has been rolledback
		if self.flags.new_file:
			self._delete_file_on_disk()
			self.flags.pop("new_file")
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
				self.flags.pop("original_content")

		# used in case file path (File.file_url) has been changed
		if self.flags.original_path:
			target = self.flags.original_path["old"]
			source = self.flags.original_path["new"]
			shutil.move(source, target)
			self.flags.pop("original_path")

	def get_name_based_on_parent_folder(self) -> str | None:
		if self.folder:
			return os.path.join(self.folder, self.file_name)

	def get_successors(self):
		return frappe.get_all("File", filters={"folder": self.name}, pluck="name")

	def validate_file_path(self):
		if self.is_remote_file:
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

		if not self.file_url.startswith(("/files/", "/private/files/")):
			# Probably an invalid URL since it doesn't start with http either
			frappe.throw(
				_("URL must start with http:// or https://"),
				title=_("Invalid URL"),
			)

	def handle_is_private_changed(self):
		if self.is_remote_file:
			return

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
		frappe.local.rollback_observers.append(self)

		self.file_url = updated_file_url
		update_existing_file_docs(self)

		if (
			not self.attached_to_doctype
			or not self.attached_to_name
			or not self.fetch_attached_to_field(old_file_url)
		):
			return

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
						frappe.bold(attachment_limit), self.attached_to_doctype, self.attached_to_name
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

	def validate_file_on_disk(self):
		"""Validates existence file"""
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
				"name": ("!=", self.name),
			}
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

	def set_file_name(self):
		if not self.file_name and not self.file_url:
			frappe.throw(
				_("Fields `file_name` or `file_url` must be set for File"), exc=frappe.MandatoryError
			)
		elif not self.file_name and self.file_url:
			self.file_name = self.file_url.split("/")[-1]
		else:
			self.file_name = re.sub(r"/", "", self.file_name)

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

	def make_thumbnail(
		self,
		set_as_thumbnail: bool = True,
		width: int = 300,
		height: int = 300,
		suffix: str = "small",
		crop: bool = False,
	) -> str:
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

	def _delete_file_on_disk(self):
		"""If file not attached to any other record, delete it"""
		on_disk_file_not_shared = self.content_hash and not frappe.get_all(
			"File",
			filters={"content_hash": self.content_hash, "name": ["!=", self.name]},
			limit=1,
		)
		if on_disk_file_not_shared:
			self.delete_file_data_content()
		else:
			self.delete_file_data_content(only_thumbnail=True)

	def unzip(self) -> list["File"]:
		"""Unzip current file and replace it by its children"""
		if not self.file_url.endswith(".zip"):
			frappe.throw(_("{0} is not a zip file").format(self.file_name))

		zip_path = self.get_full_path()

		files = []
		with zipfile.ZipFile(zip_path) as z:
			for file in z.filelist:
				if file.is_dir() or file.filename.startswith("__MACOSX/"):
					# skip directories and macos hidden directory
					continue

				filename = os.path.basename(file.filename)
				if filename.startswith("."):
					# skip hidden files
					continue

				file_doc = frappe.new_doc("File")
				try:
					file_doc.content = z.read(file.filename)
				except zipfile.BadZipFile:
					frappe.throw(_("{0} is a not a valid zip file").format(self.file_name))
				file_doc.file_name = filename
				file_doc.folder = self.folder
				file_doc.is_private = self.is_private
				file_doc.attached_to_doctype = self.attached_to_doctype
				file_doc.attached_to_name = self.attached_to_name
				file_doc.save()
				files.append(file_doc)

		frappe.delete_doc("File", self.name)
		return files

	def exists_on_disk(self):
		return os.path.exists(self.get_full_path())

	def get_content(self) -> bytes:
		if self.is_folder:
			frappe.throw(_("Cannot get file contents of a Folder"))

		if self.get("content"):
			self._content = self.content
			if self.decode:
				self._content = decode_file_content(self._content)
				self.decode = False
			# self.content = None # TODO: This needs to happen; make it happen somehow
			return self._content

		if self.file_url:
			self.validate_file_url()
		file_path = self.get_full_path()

		# read the file
		with open(file_path, mode="rb") as f:
			self._content = f.read()
			try:
				# for plain text files
				self._content = self._content.decode()
			except UnicodeDecodeError:
				# for .png, .jpg, etc
				pass

		return self._content

	def get_full_path(self):
		"""Returns file path from given file name"""

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

		with open(file_path, "wb+") as f:
			f.write(self._content)
			os.fsync(f.fileno())

		frappe.local.rollback_observers.append(self)

		return file_path

	def save_file(
		self,
		content: bytes | str | None = None,
		decode=False,
		ignore_existing_file_check=False,
		overwrite=False,
	):
		if self.is_remote_file:
			return

		if not self.flags.new_file:
			self.flags.original_content = self.get_content()

		if content:
			self.content = content
			self.decode = decode
			self.get_content()

		if not self._content:
			return

		file_exists = False
		duplicate_file = None

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

		# check if a file exists with the same content hash and is also in the same folder (public or private)
		if not ignore_existing_file_check:
			duplicate_file = frappe.get_value(
				"File",
				{"content_hash": self.content_hash, "is_private": self.is_private},
				["file_url", "name"],
				as_dict=True,
			)

		if duplicate_file:
			file_doc: "File" = frappe.get_cached_doc("File", duplicate_file.name)
			if file_doc.exists_on_disk():
				self.file_url = duplicate_file.file_url
				file_exists = True

		if not file_exists:
			if not overwrite:
				self.file_name = generate_file_name(
					name=self.file_name,
					suffix=self.content_hash[-6:],
					is_private=self.is_private,
				)
			call_hook_method("before_write_file", file_size=self.file_size)
			write_file_method = get_hook_method("write_file")
			if write_file_method:
				return write_file_method(self)
			return self.save_file_on_filesystem()

	def save_file_on_filesystem(self):
		if self.is_private:
			self.file_url = f"/private/files/{self.file_name}"
		else:
			self.file_url = f"/files/{self.file_name}"

		fpath = self.write_file()

		return {"file_name": os.path.basename(fpath), "file_url": self.file_url}

	def check_max_file_size(self):
		from frappe.core.api.file import get_max_file_size

		max_file_size = get_max_file_size()
		file_size = len(self._content or b"")

		if file_size > max_file_size:
			frappe.throw(
				_("File size exceeded the maximum allowed size of {0} MB").format(max_file_size / 1048576),
				exc=MaxFileSizeReachedError,
			)

		return file_size

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

	def is_downloadable(self):
		return has_permission(self, "read")

	def get_extension(self):
		"""returns split filename and extension"""
		return os.path.splitext(self.file_name)

	def create_attachment_record(self):
		icon = ' <i class="fa fa-lock text-warning"></i>' if self.is_private else ""
		file_url = (
			quote(frappe.safe_encode(self.file_url), safe="/:") if self.file_url else self.file_name
		)
		file_name = self.file_name or self.file_url

		self.add_comment_in_reference_doc(
			"Attachment",
			_("Added {0}").format(f"<a href='{file_url}' target='_blank'>{file_name}</a>{icon}"),
		)

	def add_comment_in_reference_doc(self, comment_type, text):
		if self.attached_to_doctype and self.attached_to_name:
			try:
				doc = frappe.get_doc(self.attached_to_doctype, self.attached_to_name)
				doc.add_comment(comment_type, text)
			except frappe.DoesNotExistError:
				frappe.clear_messages()

	def set_is_private(self):
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

		self.save_file(content=optimized_content, overwrite=True)
		self.save()

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


def on_doctype_update():
	frappe.db.add_index("File", ["attached_to_doctype", "attached_to_name"])


def has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user

	if ptype == "create":
		return frappe.has_permission("File", "create", user=user)

	if not doc.is_private or (user != "Guest" and doc.owner == user) or user == "Administrator":
		return True

	if doc.attached_to_doctype and doc.attached_to_name:
		attached_to_doctype = doc.attached_to_doctype
		attached_to_name = doc.attached_to_name

		ref_doc = frappe.get_doc(attached_to_doctype, attached_to_name)

		if ptype in ["write", "create", "delete"]:
			return ref_doc.has_permission("write")
		else:
			return ref_doc.has_permission("read")

	return False


def get_permission_query_conditions(user: str = None) -> str:
	user = user or frappe.session.user
	if user == "Administrator":
		return ""

	readable_doctypes = ", ".join(repr(dt) for dt in get_doctypes_with_read())
	return f"""
		(`tabFile`.`is_private` = 0)
		OR (`tabFile`.`attached_to_doctype` IS NULL AND `tabFile`.`owner` = {user !r})
		OR (`tabFile`.`attached_to_doctype` IN ({readable_doctypes}))
	"""


# Note: kept at the end to not cause circular, partial imports & maintain backwards compatibility
from frappe.core.api.file import *
