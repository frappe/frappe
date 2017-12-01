# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""
record of files

naming for same name files: file.gif, file-1.gif, file-2.gif etc
"""

import frappe
import json
import os
import shutil
import requests
import requests.exceptions
import mimetypes, imghdr

from frappe.utils.file_manager import delete_file_data_content, get_content_hash, get_random_filename
from frappe import _
from frappe.utils.nestedset import NestedSet
from frappe.utils import strip, get_files_path
from PIL import Image, ImageOps
from six import StringIO, string_types
from six.moves.urllib.parse import unquote
import zipfile

class FolderNotEmpty(frappe.ValidationError): pass

exclude_from_linked_with = True

class File(NestedSet):
	nsm_parent_field = 'folder'
	no_feed_on_delete = True

	def before_insert(self):
		frappe.local.rollback_observers.append(self)
		self.set_folder_name()

	def get_name_based_on_parent_folder(self):
		path = get_breadcrumbs(self.folder)
		folder_name = frappe.get_value("File", self.folder, "file_name")
		return "/".join([d.file_name for d in path] + [folder_name, self.file_name])

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
		self.update_parent_folder_size()

	def after_rename(self, olddn, newdn, merge=False):
		for successor in self.get_successor():
			setup_folder_path(successor, self.name)

	def get_successor(self):
		return frappe.db.sql_list("select name from tabFile where folder='%s'"%self.name) or []

	def validate(self):
		if self.is_new():
			self.validate_duplicate_entry()
		self.validate_folder()

		if not self.flags.ignore_file_validate:
			self.validate_file()
			self.generate_content_hash()

		self.set_folder_size()

		if frappe.db.exists('File', {'name': self.name, 'is_folder': 0}):
			if not self.is_folder and (self.is_private != self.db_get('is_private')):
				old_file_url = self.file_url
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
			if self.attached_to_doctype and self.attached_to_name and \
				frappe.db.get_value(self.attached_to_doctype, self.attached_to_name, "image") == old_file_url:
				frappe.db.set_value(self.attached_to_doctype, self.attached_to_name, "image", self.file_url)

	def set_folder_size(self):
		"""Set folder size if folder"""
		if self.is_folder and not self.is_new():
			self.file_size = self.get_folder_size()
			self.db_set('file_size', self.file_size)

			for folder in self.get_ancestors():
				frappe.db.set_value("File", folder, "file_size", self.get_folder_size(folder))

	def get_folder_size(self, folder=None):
		"""Returns folder size for current folder"""
		if not folder:
			folder = self.name
		file_size =  frappe.db.sql("""select sum(ifnull(file_size,0))
			from tabFile where folder=%s """, (folder))[0][0]

		return file_size

	def update_parent_folder_size(self):
		"""Update size of parent folder"""
		if self.folder and not self.is_folder: # it not home
			frappe.get_doc("File", self.folder).set_folder_size()

	def set_folder_name(self):
		"""Make parent folders if not exists based on reference doctype and name"""
		if self.attached_to_doctype and not self.folder:
			self.folder = frappe.db.get_value("File", {"is_attachments_folder": 1})

	def validate_folder(self):
		if not self.is_home_folder and not self.folder and \
			not self.flags.ignore_folder_validate:
			frappe.throw(_("Folder is mandatory"))

	def validate_file(self):
		"""Validates existence of public file
		TODO: validate for private file
		"""
		if (self.file_url or "").startswith("/files/"):
			if not self.file_name:
				self.file_name = self.file_url.split("/files/")[-1]

			if not os.path.exists(get_files_path(frappe.as_unicode(self.file_name.lstrip("/")))):
				frappe.throw(_("File {0} does not exist").format(self.file_url), IOError)

	def validate_duplicate_entry(self):
		if not self.flags.ignore_duplicate_entry_error and not self.is_folder:
			# check duplicate name

			# check duplicate assignement
			n_records = frappe.db.sql("""select name from `tabFile`
				where content_hash=%s
				and name!=%s
				and attached_to_doctype=%s
				and attached_to_name=%s""", (self.content_hash, self.name, self.attached_to_doctype,
					self.attached_to_name))
			if len(n_records) > 0:
				self.duplicate_entry = n_records[0][0]
				frappe.throw(frappe._("Same file has already been attached to the record"), frappe.DuplicateEntryError)

	def generate_content_hash(self):
		if self.content_hash or not self.file_url:
			return

		if self.file_url.startswith("/files/"):
			try:
				with open(get_files_path(self.file_name.lstrip("/")), "r") as f:
					self.content_hash = get_content_hash(f.read())
			except IOError:
				frappe.msgprint(_("File {0} does not exist").format(self.file_url))
				raise

	def on_trash(self):
		if self.is_home_folder or self.is_attachments_folder:
			frappe.throw(_("Cannot delete Home and Attachments folders"))
		self.check_folder_is_empty()
		self.check_reference_doc_permission()
		super(File, self).on_trash()
		self.delete_file()

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
				except (requests.exceptions.HTTPError, requests.exceptions.SSLError, IOError):
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

	def after_delete(self):
		self.update_parent_folder_size()

	def check_folder_is_empty(self):
		"""Throw exception if folder is not empty"""
		files = frappe.get_all("File", filters={"folder": self.name}, fields=("name", "file_name"))

		if self.is_folder and files:
			frappe.throw(_("Folder {0} is not empty").format(self.name), FolderNotEmpty)

	def check_reference_doc_permission(self):
		"""Check if permission exists for reference document"""
		if not frappe.db.exists(self.attached_to_doctype, self.attached_to_name):
			# document is already deleted before deleting attachment
			return

		if self.attached_to_name:
			# check persmission
			try:
				if not self.flags.ignore_permissions and \
					not frappe.has_permission(self.attached_to_doctype,
						"write", self.attached_to_name):
					frappe.throw(frappe._("Cannot delete file as it belongs to {0} {1} for which you do not have permissions").format(self.attached_to_doctype, self.attached_to_name),
						frappe.PermissionError)
			except frappe.DoesNotExistError:
				pass

	def delete_file(self):
		"""If file not attached to any other record, delete it"""
		if self.file_name and self.content_hash and (not frappe.db.count("File",
			{"content_hash": self.content_hash, "name": ["!=", self.name]})):
				delete_file_data_content(self)

		elif self.file_url:
			delete_file_data_content(self, only_thumbnail=True)

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

		frappe.delete_doc('File', self.name)

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
def get_breadcrumbs(folder):
	"""returns name, file_name of parent folder"""
	values = frappe.db.get_value("File", folder, ["lft", "rgt"], as_dict=True)
	if not values:
		frappe.throw(_("Folder {0} does not exist").format(folder))

	return frappe.db.sql("""select name, file_name from tabFile
		where lft < %s and rgt > %s order by lft asc""", (values.lft, values.rgt), as_dict=1)

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
		frappe.rename_doc("File", file.name, file.get_name_based_on_parent_folder(), ignore_permissions=True)

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
		frappe.msgprint(_("Unable to read file format for {0}").format(file_url))
		raise

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

	image = Image.open(StringIO(r.content))

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

def check_file_permission(file_url):
	for file in frappe.get_all("File", filters={"file_url": file_url, "is_private": 1}, fields=["name", "attached_to_doctype", "attached_to_name"]):

		if (frappe.has_permission("File", ptype="read", doc=file.name)
			or frappe.has_permission(file.attached_to_doctype, ptype="read", doc=file.attached_to_name)):
			return True

	raise frappe.PermissionError

@frappe.whitelist()
def unzip_file(name):
	'''Unzip the given file and make file records for each of the extracted files'''
	file_obj = frappe.get_doc('File', name)
	file_obj.unzip()
