# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
from frappe.utils.file_manager import save_file, get_file, get_files_path
from frappe import _
from frappe.core.doctype.file.file import move_file
import json
# test_records = frappe.get_test_records('File')

class TestFile(unittest.TestCase):
	def setUp(self):
		self.delete_test_data()
		self.upload_file()
		
	def delete_test_data(self):
		for file_name in ["folder_copy.txt", "file_copy.txt", "Test Folder 2"]:
			file_name = frappe.db.get_value("File", {"file_name": file_name}, "name")
			if file_name:
				file = frappe.get_doc("File", file_name)
				ancestors = file.get_ancestors()
				file.delete()
				self.delete_ancestors(ancestors)

	def delete_ancestors(self, ancestors):
		for folder in ancestors:
			if folder != "Home":
				folder = frappe.get_doc("File", folder)
				folder.delete()

	def upload_file(self):
		self.saved_file = save_file('file_copy.txt', "Testing file copy example.",\
			 "", "", self.get_folder("Test Folder 1", "Home").name)
		self.saved_filename = get_files_path(self.saved_file.file_name)
	
	def get_folder(self, folder_name, parent_folder="Home"):
		return frappe.get_doc({
			"doctype": "File",
			"file_name": _(folder_name),
			"is_folder": 1,
			"folder": _(parent_folder)
		}).insert()

	def tests_after_upload(self):
		self.assertEqual(self.saved_file.folder, _("Home/Test Folder 1"))
		
		folder_size = frappe.db.get_value("File", _("Home/Test Folder 1"), "file_size")
		saved_file_size = frappe.db.get_value("File", self.saved_file.name, "file_size")
		
		self.assertEqual(folder_size, saved_file_size)
		
	def test_file_copy(self):
		folder = self.get_folder("Test Folder 2", "Home")
		
		file = frappe.get_doc("File", "/files/file_copy.txt")
		
		file_dict = [{"name": file.name}]
		
		move_file(json.dumps(file_dict), folder.name, file.folder)
		    
		file = frappe.get_doc("File", "/files/file_copy.txt")
		
		self.assertEqual(_("Home/Test Folder 2"), file.folder)
		self.assertEqual(frappe.db.get_value("File", _("Home/Test Folder 2"), "file_size"), file.file_size)
		self.assertEqual(frappe.db.get_value("File", _("Home/Test Folder 1"), "file_size"), None)
		
	def test_folder_copy(self):
		folder = self.get_folder("Test Folder 2", "Home")
		folder = self.get_folder("Test Folder 3", "Home/Test Folder 2")
		
		self.saved_file = save_file('folder_copy.txt', "Testing folder copy example.", "", "", folder.name)
		
		file_dict = [{"name": folder.name}]
		
		move_file(json.dumps(file_dict), 'Home/Test Folder 1', folder.folder)
		    
		file = frappe.get_doc("File", "/files/folder_copy.txt")
		
		self.assertEqual(_("Home/Test Folder 1/Test Folder 3"), file.folder)
		self.assertEqual(frappe.db.get_value("File", _("Home/Test Folder 1"), "file_size"), file.file_size)
		self.assertEqual(frappe.db.get_value("File", _("Home/Test Folder 2"), "file_size"), None)
		
	def test_non_parent_folder(self):
		d = frappe.get_doc({
			"doctype": "File",
			"file_name": _("Test_Folder"),
			"is_folder": 1
		})
		
		self.assertRaises(frappe.ValidationError, d.save)
		
	def test_on_delete(self):
		file = frappe.get_doc("File", "/files/file_copy.txt")
		file.delete()
		
		self.assertEqual(frappe.db.get_value("File", _("Home/Test Folder 1"), "file_size"), None)
		
		folder = self.get_folder("Test Folder 3", "Home/Test Folder 1")
		self.saved_file = save_file('folder_copy.txt', "Testing folder copy example.", "", "", folder.name)

		folder = frappe.get_doc("File", "Home/Test Folder 1/Test Folder 3")
		self.assertRaises(frappe.ValidationError, folder.delete)
		