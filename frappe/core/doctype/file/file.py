# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""
record of files

naming for same name files: file.gif, file-1.gif, file-2.gif etc
"""

import frappe, frappe.utils
from frappe.utils.file_manager import delete_file_data_content
from frappe import _

from frappe.utils.nestedset import NestedSet
import json

class FolderNotEmpty(frappe.ValidationError): pass

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
			self.name = self.file_url

	def after_insert(self):
		self.update_parent_folder_size()
	
	def after_rename(self, olddn, newdn, merge=False):
		for successor in self.get_successor():
			setup_folder_path(successor, self.name)
	
	def get_successor(self):
		return frappe.db.sql_list("select name from tabFile where folder='%s'"%self.name) or []
	
	def validate(self):
		self.validate_duplicate_entry()
		self.validate_folder()
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
			frappe.get_doc("File", self.folder).save()

	def set_folder_name(self):
		"""Make parent folders if not exists based on reference doctype and name"""
		if self.attached_to_doctype and not self.folder:
			self.folder = self.get_parent_folder_name()

	def get_parent_folder_name(self):
		"""Returns parent folder name. If not exists, then make"""
		doctype_folder_name = self.get_doctype_folder_name()
		parent_folder_name = frappe.db.get_value("File", {"file_name": self.attached_to_name,
			"is_folder": 1, "folder": doctype_folder_name})

		return self.make_folder(parent_folder_name, doctype_folder_name,
			self.attached_to_name)

	def get_doctype_folder_name(self):
		"""Returns doctype folder name. If not exists, then make"""
		module_folder_name = self.get_module_folder_name()
		doctype_folder_name = frappe.db.get_value("File", {"file_name": self.attached_to_doctype,
			"is_folder": 1, "folder": module_folder_name})

		return self.make_folder(doctype_folder_name, module_folder_name,
			_(self.attached_to_doctype, frappe.db.get_default("lang")))

	def get_module_folder_name(self):
		"""Returns module folder name. If not exists, then make"""
		if self.attached_to_doctype:
			module = frappe.db.get_value("DocType", self.attached_to_doctype, "module")

		home_folder_name = frappe.db.get_value("File", {"is_home_folder": 1})

		module_folder_name = frappe.db.get_value("File", {"file_name": module,
			"is_folder": 1, "folder": home_folder_name})

		return self.make_folder(module_folder_name, home_folder_name, _(module,
			frappe.db.get_default("lang")))

	def make_folder(self, name, folder, file_name):
		if not name:
			# parent folder
			file = frappe.get_doc({
				"doctype": "File",
				"is_folder": 1,
				"file_name": file_name,
				"folder": folder
			}).insert()

			name = file.name

		return name

	def validate_folder(self):
		if not self.is_home_folder and not self.folder and \
			not self.flags.ignore_folder_validate:
			frappe.throw(_("Folder is mandatory"))

	def validate_duplicate_entry(self):
		if not self.flags.ignore_duplicate_entry_error:
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

	def on_trash(self):
		self.check_folder_is_empty()
		self.check_reference_doc_permission()
		super(File, self).on_trash()
		self.delete_file()

	def after_delete(self):
		self.update_parent_folder_size()

	def check_folder_is_empty(self):
		"""Throw exception if folder is not empty"""
		if self.is_folder and frappe.get_all("File", filters={"folder": self.name}):
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

	def on_rollback(self):
		self.on_trash()

def on_doctype_update():
	frappe.db.add_index("File", ["attached_to_doctype", "attached_to_name"])

def make_home_folder():
	frappe.get_doc({
		"doctype": "File",
		"is_folder": 1,
		"is_home_folder": 1,
		"file_name": _("Home")
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
	for file_obj in json.loads(file_list):
		setup_folder_path(file_obj.get("name"), new_parent)

	# recalculate sizes
	frappe.get_doc("File", old_parent).save()
	frappe.get_doc("File", new_parent).save()

	return "File(s) has been moved successfully!!"
	
def setup_folder_path(filename, new_parent):
	file = frappe.get_doc("File", filename)
	file.folder = new_parent
	file.save()
	
	if file.is_folder:
		frappe.rename_doc("File", file.name, file.get_name_based_on_parent_folder())