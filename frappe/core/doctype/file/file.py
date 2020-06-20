# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

"""
record of files

naming for same name files: file.gif, file-1.gif, file-2.gif etc
"""

from __future__ import unicode_literals

import base64
import hashlib
import imghdr
import io
import json
import mimetypes
import os
import re
import shutil
import zipfile

import requests
import requests.exceptions
from PIL import Image, ImageFile, ImageOps
from six import PY2, StringIO, string_types, text_type
from six.moves.urllib.parse import quote, unquote

import frappe
from frappe import _, conf
from frappe.model.document import Document
from frappe.utils import call_hook_method, cint, cstr, encode, get_files_path, get_hook_method, random_string, strip


class MaxFileSizeReachedError(frappe.ValidationError):
	pass

class FolderNotEmpty(frappe.ValidationError):
	pass

exclude_from_linked_with = True
ImageFile.LOAD_TRUNCATED_IMAGES = True


class File(Document):
	no_feed_on_delete = True

	def before_insert(self):
		frappe.local.rollback_observers.append(self)
		self.set_folder_name()
		if self.file_name:
			self.file_name = re.sub(r'/', '', self.file_name)
		self.content = self.get("content", None)
		self.decode = self.get("decode", False)
		if self.content:
			self.save_file(content=self.content, decode=self.decode)

	def get_name_based_on_parent_folder(self):
		if self.folder:
			return "/".join([self.folder, self.file_name])

	def autoname(self):
		"""Set name for folder"""
		if self.is_folder:
			if self.folder:
				self.name = self.get_name_based_on_parent_folder()
			else:
				# home
				self.name = self.file_name
		else:
			self.name = frappe.generate_hash("", 10)

	def after_insert(self):
		if not self.is_folder:
			self.add_comment_in_reference_doc('Attachment',
				_('Added {0}').format("<a href='{file_url}' target='_blank'>{file_name}</a>{icon}".format(**{
					"icon": ' <i class="fa fa-lock text-warning"></i>' if self.is_private else "",
					"file_url": quote(self.file_url) if self.file_url else self.file_name,
					"file_name": self.file_name or self.file_url
				})))

	def after_rename(self, olddn, newdn, merge=False):
		for successor in self.get_successor():
			setup_folder_path(successor[0], self.name)

	def get_successor(self):
		return frappe.db.get_values(doctype='File',
						filters={'folder': self.name},
						fieldname='name')

	def validate(self):
		if self.is_new():
			self.set_is_private()
			self.set_file_name()
			self.validate_duplicate_entry()
		self.validate_folder()

		if not self.file_url and not self.flags.ignore_file_validate:
			if not self.is_folder:
				self.validate_file()
			self.generate_content_hash()

		self.validate_url()

		if frappe.db.exists('File', {'name': self.name, 'is_folder': 0}):
			old_file_url = self.file_url
			if not self.is_folder and (self.is_private != self.db_get('is_private')):
				private_files = frappe.get_site_path('private', 'files')
				public_files = frappe.get_site_path('public', 'files')

				if not self.is_private:
					shutil.move(os.path.join(private_files, self.file_name),
						os.path.join(public_files, self.file_name))

					self.file_url = "/files/{0}".format(self.file_name)

				else:
					shutil.move(os.path.join(public_files, self.file_name),
						os.path.join(private_files, self.file_name))

					self.file_url = "/private/files/{0}".format(self.file_name)


			# update documents image url with new file url
			if self.attached_to_doctype and self.attached_to_name:
				if not self.attached_to_field:
					field_name = None
					reference_dict = frappe.get_doc(self.attached_to_doctype, self.attached_to_name).as_dict()
					for key, value in reference_dict.items():
						if value == old_file_url:
							field_name = key
							break
					self.attached_to_field = field_name
				if self.attached_to_field:
					frappe.db.set_value(self.attached_to_doctype, self.attached_to_name,
						self.attached_to_field, self.file_url)

		if self.file_url and (self.is_private != self.file_url.startswith('/private')):
			frappe.throw(_('Invalid file URL. Please contact System Administrator.'))

	def set_folder_name(self):
		"""Make parent folders if not exists based on reference doctype and name"""
		if self.attached_to_doctype and not self.folder:
			self.folder = frappe.db.get_value("File", {"is_attachments_folder": 1})

	def validate_folder(self):
		if not self.is_home_folder and not self.folder and \
			not self.flags.ignore_folder_validate:
			self.folder = "Home"

	def validate_file(self):
		"""Validates existence of public file
		TODO: validate for private file
		"""
		full_path = self.get_full_path()

		if full_path.startswith('http'):
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
				'content_hash': self.content_hash,
				'is_private': self.is_private,
				'name': ('!=', self.name)
			}
			if self.attached_to_doctype and self.attached_to_name:
				filters.update({
					'attached_to_doctype': self.attached_to_doctype,
					'attached_to_name': self.attached_to_name
				})
			duplicate_file = frappe.db.get_value('File', filters, ['name', 'file_url'], as_dict=1)

			if duplicate_file:
				duplicate_file_doc = frappe.get_cached_doc('File', duplicate_file.name)
				if duplicate_file_doc.exists_on_disk():
					# if it is attached to a document then throw FileAlreadyAttachedException
					if self.attached_to_doctype and self.attached_to_name:
						self.duplicate_entry = duplicate_file.name
						frappe.throw(_("Same file has already been attached to the record"),
							frappe.FileAlreadyAttachedException)
					# else just use the url, to avoid uploading a duplicate
					else:
						self.file_url = duplicate_file.file_url

	def set_file_name(self):
		if not self.file_name and self.file_url:
			self.file_name = self.file_url.split('/')[-1]
		else:
			self.file_name = re.sub(r'/', '', self.file_name)

	def generate_content_hash(self):
		if self.content_hash or not self.file_url or self.file_url.startswith('http'):
			return
		file_name = self.file_url.split('/')[-1]
		try:
			with open(get_files_path(file_name, is_private=self.is_private), "rb") as f:
				self.content_hash = get_content_hash(f.read())
		except IOError:
			frappe.msgprint(_("File {0} does not exist").format(self.file_url))
			raise

	def on_trash(self):
		if self.is_home_folder or self.is_attachments_folder:
			frappe.throw(_("Cannot delete Home and Attachments folders"))
		self.check_folder_is_empty()
		self.call_delete_file()
		if not self.is_folder:
			self.add_comment_in_reference_doc('Attachment Removed', _("Removed {0}").format(self.file_name))

	def make_thumbnail(self, set_as_thumbnail=True, width=300, height=300, suffix="small", crop=False):
		if self.file_url:
			if self.file_url.startswith("/files"):
				try:
					image, filename, extn = get_local_image(self.file_url)
				except IOError:
					return

			else:
				try:
					image, filename, extn = get_web_image(self.file_url)
				except (requests.exceptions.HTTPError, requests.exceptions.SSLError, IOError, TypeError):
					return

			size = width, height
			if crop:
				image = ImageOps.fit(image, size, Image.ANTIALIAS)
			else:
				image.thumbnail(size, Image.ANTIALIAS)

			thumbnail_url = filename + "_" + suffix + "." + extn

			path = os.path.abspath(frappe.get_site_path("public", thumbnail_url.lstrip("/")))

			try:
				image.save(path)

				if set_as_thumbnail:
					self.db_set("thumbnail_url", thumbnail_url)

				self.db_set("thumbnail_url", thumbnail_url)
			except IOError:
				frappe.msgprint(_("Unable to write file format for {0}").format(path))
				return

			return thumbnail_url

	def check_folder_is_empty(self):
		"""Throw exception if folder is not empty"""
		files = frappe.get_all("File", filters={"folder": self.name}, fields=("name", "file_name"))

		if self.is_folder and files:
			frappe.throw(_("Folder {0} is not empty").format(self.name), FolderNotEmpty)

	def call_delete_file(self):
		"""If file not attached to any other record, delete it"""
		if self.file_name and self.content_hash and (not frappe.db.count("File",
			{"content_hash": self.content_hash, "name": ["!=", self.name]})):
				self.delete_file_data_content()
		elif self.file_url:
			self.delete_file_data_content(only_thumbnail=True)

	def on_rollback(self):
		self.flags.on_rollback = True
		self.on_trash()

	def unzip(self):
		'''Unzip current file and replace it by its children'''
		if not ".zip" in self.file_name:
			frappe.msgprint(_("Not a zip file"))
			return

		zip_path = frappe.get_site_path(self.file_url.strip('/'))
		base_url = os.path.dirname(self.file_url)

		files = []
		with zipfile.ZipFile(zip_path) as zf:
			zf.extractall(os.path.dirname(zip_path))
			for info in zf.infolist():
				if not info.filename.startswith('__MACOSX'):
					file_url = file_url = base_url + '/' + info.filename
					file_name = frappe.db.get_value('File', dict(file_url=file_url))
					if file_name:
						file_doc = frappe.get_doc('File', file_name)
					else:
						file_doc = frappe.new_doc("File")
					file_doc.file_name = info.filename
					file_doc.file_size = info.file_size
					file_doc.folder = self.folder
					file_doc.is_private = self.is_private
					file_doc.file_url = file_url
					file_doc.attached_to_doctype = self.attached_to_doctype
					file_doc.attached_to_name = self.attached_to_name
					file_doc.save()
					files.append(file_doc)

		frappe.delete_doc('File', self.name)
		return files


	def get_file_url(self):
		data = frappe.db.get_value("File", self.file_data_name, ["file_name", "file_url"], as_dict=True)
		return data.file_url or data.file_name

	def exists_on_disk(self):
		exists = os.path.exists(self.get_full_path())
		return exists


	def get_content(self):
		"""Returns [`file_name`, `content`] for given file name `fname`"""
		if self.get('content'):
			return self.content
		file_path = self.get_full_path()

		# read the file
		if PY2:
			with open(encode(file_path)) as f:
				content = f.read()
		else:
			with io.open(encode(file_path), mode='rb') as f:
				content = f.read()
				try:
					# for plain text files
					content = content.decode()
				except UnicodeDecodeError:
					# for .png, .jpg, etc
					pass

		return content

	def get_full_path(self):
		"""Returns file path from given file name"""

		file_path = self.file_url or self.file_name

		if "/" not in file_path:
			file_path = "/files/" + file_path

		if file_path.startswith("/private/files/"):
			file_path = get_files_path(*file_path.split("/private/files/", 1)[1].split("/"), is_private=1)

		elif file_path.startswith("/files/"):
			file_path = get_files_path(*file_path.split("/files/", 1)[1].split("/"))

		elif file_path.startswith("http"):
			pass

		elif not self.file_url:
			frappe.throw(_("There is some problem with the file url: {0}").format(file_path))

		return file_path

	def write_file(self):
		"""write file to disk with a random name (to compare)"""
		file_path = get_files_path(is_private=self.is_private)

		# create directory (if not exists)
		frappe.create_folder(file_path)
		# write the file
		self.content = self.get_content()
		if isinstance(self.content, text_type):
			self.content = self.content.encode()
		with open(os.path.join(file_path.encode('utf-8'), self.file_name.encode('utf-8')), 'wb+') as f:
			f.write(self.content)

		return get_files_path(self.file_name, is_private=self.is_private)

	def get_file_doc(self):
		'''returns File object (Document) from given parameters or form_dict'''
		r = frappe.form_dict

		if self.file_url is None: self.file_url = r.file_url
		if self.file_name is None: self.file_name = r.file_name
		if self.attached_to_doctype is None: self.attached_to_doctype = r.doctype
		if self.attached_to_name is None: self.attached_to_name = r.docname
		if self.attached_to_field is None: self.attached_to_field = r.docfield
		if self.folder is None: self.folder = r.folder
		if self.is_private is None: self.is_private = r.is_private

		if r.filedata:
			file_doc = self.save_uploaded()

		elif r.file_url:
			file_doc = self.save()

		return file_doc


	def save_uploaded(self):
		self.content = self.get_uploaded_content()
		if self.content:
			return self.save()
		else:
			raise Exception


	def validate_url(self, df=None):
		if self.file_url:
			if not self.file_url.startswith(("http://", "https://", "/files/", "/private/files/")):
				frappe.throw(_("URL must start with 'http://' or 'https://'"))
				return

			if not self.file_url.startswith(("http://", "https://")):
				# local file
				root_files_path = get_files_path(is_private=self.is_private)
				if not os.path.commonpath([root_files_path]) == os.path.commonpath([root_files_path, self.get_full_path()]):
					# basically the file url is skewed to not point to /files/ or /private/files
					frappe.throw(_("{0} is not a valid file url").format(self.file_url))
			self.file_url = unquote(self.file_url)
			self.file_size = frappe.form_dict.file_size or self.file_size


	def get_uploaded_content(self):
		# should not be unicode when reading a file, hence using frappe.form
		if 'filedata' in frappe.form_dict:
			if "," in frappe.form_dict.filedata:
				frappe.form_dict.filedata = frappe.form_dict.filedata.rsplit(",", 1)[1]
			frappe.uploaded_content = base64.b64decode(frappe.form_dict.filedata)
			return frappe.uploaded_content
		elif self.content:
			return self.content
		frappe.msgprint(_('No file attached'))
		return None


	def save_file(self, content=None, decode=False, ignore_existing_file_check=False):
		file_exists = False
		self.content = content
		if decode:
			if isinstance(content, text_type):
				self.content = content.encode("utf-8")

			if b"," in self.content:
				self.content = self.content.split(b",")[1]
			self.content = base64.b64decode(self.content)

		if not self.is_private:
			self.is_private = 0
		self.file_size = self.check_max_file_size()
		self.content_hash = get_content_hash(self.content)
		self.content_type = mimetypes.guess_type(self.file_name)[0]

		duplicate_file = None

		# check if a file exists with the same content hash and is also in the same folder (public or private)
		if not ignore_existing_file_check:
			duplicate_file = frappe.get_value("File", {
					"content_hash": self.content_hash,
					"is_private": self.is_private
				},
				["file_url", "name"], as_dict=True)

		if duplicate_file:
			file_doc = frappe.get_cached_doc('File', duplicate_file.name)
			if file_doc.exists_on_disk():
				self.file_url  = duplicate_file.file_url
				file_exists = True

		if os.path.exists(encode(get_files_path(self.file_name, is_private=self.is_private))):
			self.file_name = get_file_name(self.file_name, self.content_hash[-6:])

		if not file_exists:
			call_hook_method("before_write_file", file_size=self.file_size)
			write_file_method = get_hook_method('write_file')
			if write_file_method:
				return write_file_method(self)
			return self.save_file_on_filesystem()


	def save_file_on_filesystem(self):
		fpath = self.write_file()

		if self.is_private:
			self.file_url = "/private/files/{0}".format(self.file_name)
		else:
			self.file_url = "/files/{0}".format(self.file_name)

		return {
			'file_name': os.path.basename(fpath),
			'file_url': self.file_url
		}

	def get_file_data_from_hash(self):
		for name in frappe.db.sql_list("select name from `tabFile` where content_hash=%s and is_private=%s",
			(self.content_hash, self.is_private)):
			b = frappe.get_doc('File', name)
			return {k: b.get(k) for k in frappe.get_hooks()['write_file_keys']}
		return False


	def check_max_file_size(self):
		max_file_size = get_max_file_size()
		file_size = len(self.content)

		if file_size > max_file_size:
			frappe.msgprint(_("File size exceeded the maximum allowed size of {0} MB").format(
				max_file_size / 1048576),
				raise_exception=MaxFileSizeReachedError)

		return file_size


	def delete_file_data_content(self, only_thumbnail=False):
		method = get_hook_method('delete_file_data_content')
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
		return has_permission(self, 'read')

	def get_extension(self):
		'''returns split filename and extension'''
		return os.path.splitext(self.file_name)

	def add_comment_in_reference_doc(self, comment_type, text):
		if self.attached_to_doctype and self.attached_to_name:
			try:
				doc = frappe.get_doc(self.attached_to_doctype, self.attached_to_name)
				doc.add_comment(comment_type, text)
			except frappe.DoesNotExistError:
				frappe.clear_messages()

	def set_is_private(self):
		if self.file_url:
			self.is_private = cint(self.file_url.startswith('/private'))

def on_doctype_update():
	frappe.db.add_index("File", ["attached_to_doctype", "attached_to_name"])

def make_home_folder():
	home = frappe.get_doc({
		"doctype": "File",
		"is_folder": 1,
		"is_home_folder": 1,
		"file_name": _("Home")
	}).insert()

	frappe.get_doc({
		"doctype": "File",
		"folder": home.name,
		"is_folder": 1,
		"is_attachments_folder": 1,
		"file_name": _("Attachments")
	}).insert()


@frappe.whitelist()
def create_new_folder(file_name, folder):
	""" create new folder under current parent folder """
	file = frappe.new_doc("File")
	file.file_name = file_name
	file.is_folder = 1
	file.folder = folder
	file.insert()

@frappe.whitelist()
def move_file(file_list, new_parent, old_parent):

	if isinstance(file_list, string_types):
		file_list = json.loads(file_list)

	for file_obj in file_list:
		setup_folder_path(file_obj.get("name"), new_parent)

	# recalculate sizes
	frappe.get_doc("File", old_parent).save()
	frappe.get_doc("File", new_parent).save()

def setup_folder_path(filename, new_parent):
	file = frappe.get_doc("File", filename)
	file.folder = new_parent
	file.save()

	if file.is_folder:
		from frappe.model.rename_doc import rename_doc
		rename_doc("File", file.name, file.get_name_based_on_parent_folder(), ignore_permissions=True)

def get_extension(filename, extn, content):
	mimetype = None

	if extn:
		# remove '?' char and parameters from extn if present
		if '?' in extn:
			extn = extn.split('?', 1)[0]

		mimetype = mimetypes.guess_type(filename + "." + extn)[0]

	if mimetype is None or not mimetype.startswith("image/") and content:
		# detect file extension by reading image header properties
		extn = imghdr.what(filename + "." + (extn or ""), h=content)

	return extn

def get_local_image(file_url):
	file_path = frappe.get_site_path("public", file_url.lstrip("/"))

	try:
		image = Image.open(file_path)
	except IOError:
		frappe.msgprint(_("Unable to read file format for {0}").format(file_url), raise_exception=True)

	content = None

	try:
		filename, extn = file_url.rsplit(".", 1)
	except ValueError:
		# no extn
		with open(file_path, "r") as f:
			content = f.read()

		filename = file_url
		extn = None

	extn = get_extension(filename, extn, content)

	return image, filename, extn

def get_web_image(file_url):
	# download
	file_url = frappe.utils.get_url(file_url)
	r = requests.get(file_url, stream=True)
	try:
		r.raise_for_status()
	except requests.exceptions.HTTPError as e:
		if "404" in e.args[0]:
			frappe.msgprint(_("File '{0}' not found").format(file_url))
		else:
			frappe.msgprint(_("Unable to read file format for {0}").format(file_url))
		raise

	image = Image.open(StringIO(frappe.safe_decode(r.content)))

	try:
		filename, extn = file_url.rsplit("/", 1)[1].rsplit(".", 1)
	except ValueError:
		# the case when the file url doesn't have filename or extension
		# but is fetched due to a query string. example: https://encrypted-tbn3.gstatic.com/images?q=something
		filename = get_random_filename()
		extn = None

	extn = get_extension(filename, extn, r.content)
	filename = "/files/" + strip(unquote(filename))

	return image, filename, extn


def delete_file(path):
	"""Delete file from `public folder`"""
	if path:
		if ".." in path.split("/"):
			frappe.msgprint(_("It is risky to delete this file: {0}. Please contact your System Manager.").format(path))

		parts = os.path.split(path.strip("/"))
		if parts[0]=="files":
			path = frappe.utils.get_site_path("public", "files", parts[-1])

		else:
			path = frappe.utils.get_site_path("private", "files", parts[-1])

		path = encode(path)
		if os.path.exists(path):
			os.remove(path)


def remove_file(fid=None, attached_to_doctype=None, attached_to_name=None, from_delete=False):
	"""Remove file and File entry"""
	file_name = None
	if not (attached_to_doctype and attached_to_name):
		attached = frappe.db.get_value("File", fid,
			["attached_to_doctype", "attached_to_name", "file_name"])
		if attached:
			attached_to_doctype, attached_to_name, file_name = attached

	ignore_permissions, comment = False, None
	if attached_to_doctype and attached_to_name and not from_delete:
		doc = frappe.get_doc(attached_to_doctype, attached_to_name)
		ignore_permissions = doc.has_permission("write") or False
		if frappe.flags.in_web_form:
			ignore_permissions = True
		if not file_name:
			file_name = frappe.db.get_value("File", fid, "file_name")
		comment = doc.add_comment("Attachment Removed", _("Removed {0}").format(file_name))
		frappe.delete_doc("File", fid, ignore_permissions=ignore_permissions)

	return comment


def get_max_file_size():
	return cint(conf.get('max_file_size')) or 10485760


def remove_all(dt, dn, from_delete=False):
	"""remove all files in a transaction"""
	try:
		for fid in frappe.db.sql_list("""select name from `tabFile` where
			attached_to_doctype=%s and attached_to_name=%s""", (dt, dn)):
			if from_delete:
				# If deleting a doc, directly delete files
				frappe.delete_doc("File", fid, ignore_permissions=True)
			else:
				# Removes file and adds a comment in the document it is attached to
				remove_file(fid=fid, attached_to_doctype=dt, attached_to_name=dn, from_delete=from_delete)
	except Exception as e:
		if e.args[0]!=1054: raise # (temp till for patched)


def has_permission(doc, ptype=None, user=None):
	has_access = False
	user = user or frappe.session.user

	if ptype == 'create':
		has_access = frappe.has_permission('File', 'create', user=user)

	if not doc.is_private or doc.owner in [user, 'Guest'] or user == 'Administrator':
		has_access = True

	if doc.attached_to_doctype and doc.attached_to_name:
		attached_to_doctype = doc.attached_to_doctype
		attached_to_name = doc.attached_to_name

		try:
			ref_doc = frappe.get_doc(attached_to_doctype, attached_to_name)

			if ptype in ['write', 'create', 'delete']:
				has_access = ref_doc.has_permission('write')

				if ptype == 'delete' and not has_access:
					frappe.throw(_("Cannot delete file as it belongs to {0} {1} for which you do not have permissions").format(
						doc.attached_to_doctype, doc.attached_to_name),
						frappe.PermissionError)
			else:
				has_access = ref_doc.has_permission('read')
		except frappe.DoesNotExistError:
			# if parent doc is not created before file is created
			# we cannot check its permission so we will use file's permission
			pass

	return has_access


def remove_file_by_url(file_url, doctype=None, name=None):
	if doctype and name:
		fid = frappe.db.get_value("File", {
			"file_url": file_url,
			"attached_to_doctype": doctype,
			"attached_to_name": name})
	else:
		fid = frappe.db.get_value("File", {"file_url": file_url})

	if fid:
		return remove_file(fid=fid)


def get_content_hash(content):
	if isinstance(content, text_type):
		content = content.encode()
	return hashlib.md5(content).hexdigest() #nosec


def get_file_name(fname, optional_suffix):
	# convert to unicode
	fname = cstr(fname)

	f = fname.rsplit('.', 1)
	if len(f) == 1:
		partial, extn = f[0], ""
	else:
		partial, extn = f[0], "." + f[1]
	return '{partial}{suffix}{extn}'.format(partial=partial, extn=extn, suffix=optional_suffix)


@frappe.whitelist()
def download_file(file_url):
	"""
	Download file using token and REST API. Valid session or
	token is required to download private files.

	Method : GET
	Endpoint : frappe.core.doctype.file.file.download_file
	URL Params : file_name = /path/to/file relative to site path
	"""
	file_doc = frappe.get_doc("File", {"file_url": file_url})
	file_doc.check_permission("read")

	frappe.local.response.filename = os.path.basename(file_url)
	frappe.local.response.filecontent = file_doc.get_content()
	frappe.local.response.type = "download"

def extract_images_from_doc(doc, fieldname):
	content = doc.get(fieldname)
	content = extract_images_from_html(doc, content)
	if frappe.flags.has_dataurl:
		doc.set(fieldname, content)


def extract_images_from_html(doc, content):
	frappe.flags.has_dataurl = False

	def _save_file(match):
		data = match.group(1)
		data = data.split("data:")[1]
		headers, content = data.split(",")

		if "filename=" in headers:
			filename = headers.split("filename=")[-1]

			# decode filename
			if not isinstance(filename, text_type):
				filename = text_type(filename, 'utf-8')
		else:
			mtype = headers.split(";")[0]
			filename = get_random_filename(content_type=mtype)

		doctype = doc.parenttype if doc.parent else doc.doctype
		name = doc.parent or doc.name

		_file = frappe.get_doc({
			"doctype": "File",
			"file_name": filename,
			"attached_to_doctype": doctype,
			"attached_to_name": name,
			"content": content,
			"decode": True
		})
		_file.save(ignore_permissions=True)
		file_url = _file.file_url
		if not frappe.flags.has_dataurl:
			frappe.flags.has_dataurl = True

		return '<img src="{file_url}"'.format(file_url=file_url)

	if content and isinstance(content, string_types):
		content = re.sub('<img[^>]*src\s*=\s*["\'](?=data:)(.*?)["\']', _save_file, content)

	return content


def get_random_filename(extn=None, content_type=None):
	if extn:
		if not extn.startswith("."):
			extn = "." + extn

	elif content_type:
		extn = mimetypes.guess_extension(content_type)

	return random_string(7) + (extn or "")


@frappe.whitelist()
def unzip_file(name):
	'''Unzip the given file and make file records for each of the extracted files'''
	file_obj = frappe.get_doc('File', name)
	files = file_obj.unzip()
	return len(files)


@frappe.whitelist()
def get_attached_images(doctype, names):
	'''get list of image urls attached in form
	returns {name: ['image.jpg', 'image.png']}'''

	if isinstance(names, string_types):
		names = json.loads(names)

	img_urls = frappe.db.get_list('File', filters={
		'attached_to_doctype': doctype,
		'attached_to_name': ('in', names),
		'is_folder': 0
	}, fields=['file_url', 'attached_to_name as docname'])

	out = frappe._dict()
	for i in img_urls:
		out[i.docname] = out.get(i.docname, [])
		out[i.docname].append(i.file_url)

	return out


@frappe.whitelist()
def validate_filename(filename):
	from frappe.utils import now_datetime
	timestamp = now_datetime().strftime(" %Y-%m-%d %H:%M:%S")
	fname = get_file_name(filename, timestamp)
	return fname

@frappe.whitelist()
def get_files_in_folder(folder):
	return frappe.db.get_all('File',
		{ 'folder': folder },
		['name', 'file_name', 'file_url', 'is_folder', 'modified']
	)
