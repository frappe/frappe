# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""
record of files

naming for same name files: file.gif, file-1.gif, file-2.gif etc
"""

import frappe, frappe.utils
from frappe.utils.file_manager import delete_file_data_content, get_content_hash, get_random_filename
from frappe import _

from frappe.utils.nestedset import NestedSet
from frappe.utils import strip
import json
import urllib
from PIL import Image, ImageOps
import os
import requests
import requests.exceptions
import StringIO
import mimetypes, imghdr
from frappe.utils import get_files_path

class FolderNotEmpty(frappe.ValidationError): pass
class ThumbnailError(frappe.ValidationError): pass

exclude_from_linked_with = True

class File(NestedSet):
	nsm_parent_field = 'folder'
	no_feed_on_delete = True

	def before_insert(self):
		frappe.local.rollback_observers.append(self)
		self.set_folder_name()
		self.set_name()

	def get_name_based_on_parent_folder(self):
		path = get_breadcrumbs(self.folder)
		folder_name = frappe.get_value("File", self.folder, "file_name")
		return "/".join([d.file_name for d in path] + [folder_name, self.file_name])

	def set_name(self):
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

	def set_folder_size(self):
		"""Set folder size if folder"""
		if self.is_folder and not self.is_new():
			self.file_size = self.get_folder_size()
			frappe.db.set_value("File", self.name, "file_size", self.file_size)

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
			frappe.get_doc("File", self.folder).save(ignore_permissions=True)

	def set_folder_name(self):
		"""Make parent folders if not exists based on reference doctype and name"""
		if self.attached_to_doctype and not self.folder:
			self.folder = frappe.db.get_value("File", {"is_attachments_folder": 1})

	def validate_folder(self):
		if not self.is_home_folder and not self.folder and \
			not self.flags.ignore_folder_validate:
			frappe.throw(_("Folder is mandatory"))

	def validate_file(self):
		if (self.file_url or "").startswith("/files/"):
			if not self.file_name:
				self.file_name = self.file_url.split("/files/")[-1]

			if not os.path.exists(get_files_path(self.file_name.lstrip("/"))):
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

	def make_thumbnail(self):
		if self.file_url:
			if self.file_url.startswith("/files"):
				image, filename, extn = get_local_image(self.file_url)

			else:
				try:
					image, filename, extn = get_web_image(self.file_url)
				except ThumbnailError:
					frappe.msgprint("Unable to write file format for {0}".format(self.file_url))

			thumbnail = ImageOps.fit(
				image,
				(300, 300),
				Image.ANTIALIAS
			)

			thumbnail_url = filename + "_small." + extn

			path = os.path.abspath(frappe.get_site_path("public", thumbnail_url.lstrip("/")))

			try:
				thumbnail.save(path)
				self.db_set("thumbnail_url", thumbnail_url)
			except IOError:
				frappe.msgprint("Unable to write file format for {0}".format(path))

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
		if self.attached_to_name:
			# check persmission
			try:
				if not self.flags.ignore_permissions and \
					not frappe.has_permission(self.attached_to_doctype,
						"write", self.attached_to_name):
					frappe.throw(frappe._("No permission to write / remove."),
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
	lft, rgt = frappe.db.get_value("File", folder, ["lft", "rgt"])
	return frappe.db.sql("""select name, file_name from tabFile
		where lft < %s and rgt > %s order by lft asc""", (lft, rgt), as_dict=1)

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
	if isinstance(file_list, basestring):
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
		frappe.msgprint("Unable to read file format for {0}".format(file_url))
		return

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
	# downlaod
	file_url = frappe.utils.get_url(file_url)
	r = requests.get(file_url, stream=True)
	try:
		r.raise_for_status()
	except requests.exceptions.HTTPError, e:
		if "404" in e.args[0]:
			frappe.throw(_("File '{0}' not found").format(file_url))
		else:
			raise ThumbnailError

	image = Image.open(StringIO.StringIO(r.content))

	try:
		filename, extn = file_url.rsplit("/", 1)[1].rsplit(".", 1)
	except ValueError:
		# the case when the file url doesn't have filename or extension
		# but is fetched due to a query string. example: https://encrypted-tbn3.gstatic.com/images?q=something
		filename = get_random_filename()
		extn = None

	extn = get_extension(filename, extn, r.content)
	filename = "/files/" + strip(urllib.unquote(filename))

	return image, filename, extn
