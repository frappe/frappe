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
		self.delete_exist_folder()
		self.upload_file()

	def test_file_upload(self):
		self.execute_tests_after_upload()
		self.execute_test_copy_doc()
		self.execute_test_non_parent_folder()

	def delete_exist_folder(self):
		file_name = frappe.db.get_value("File", {"file_url":"/files/hello.txt"}, "name")
		if file_name:
			file = frappe.get_doc("File", file_name)
			ancestors = file.get_ancestors()
			file.delete()
			self.delete_ancestors(ancestors)
			self.execute_tests_after_trash()

	def delete_ancestors(self, ancestors):
		for folder in ancestors:
			if folder != "Home":
				folder = frappe.get_doc("File", folder)
				folder.delete()

	def execute_tests_after_trash(self):
		if frappe.db.get_value("File", _("Home/Test_Folder_Copy"), "folder"):
			file_size = frappe.db.get_value("File", _("Home/Test_Folder_Copy"), "file_size")
			self.assertEqual(file_size, 0)

	def upload_file(self):
		self.attached_to_doctype, self.attached_to_docname = self.create_event()
		self.saved_file = save_file('hello.txt', "hello world", \
			self.attached_to_doctype, self.attached_to_docname)
		self.saved_filename = get_files_path(self.saved_file.file_name)

	def create_event(self):
		event = frappe.get_doc({
			"doctype": "Event",
			"subject":"File Upload Event",
			"starts_on": "2014-01-01",
			"event_type": "Public"
		}).insert()

		return event.doctype, event.name

	def execute_tests_after_upload(self):
		self.assertTrue(frappe.db.get_value("File",
			"Home/Desk/Event/%s"%self.attached_to_docname, "is_folder"))

		self.assertEqual("Home/Desk/Event/%s"%self.attached_to_docname, \
			frappe.db.get_value("File", {"file_url":"/files/hello.txt"}, "folder"))

	def execute_test_copy_doc(self):
		folder = frappe.get_doc({
			"doctype": "File",
			"file_name": _("Test_Folder_Copy"),
			"is_folder": 1,
			"folder": _("Home")
		}).insert()
		
		file = frappe.get_doc("File", "/files/hello.txt")
		
		file_dict = [{"name": file.name}]
		move_file(json.dumps(file_dict), folder.name, file.folder)
		    
		file = frappe.get_doc("File", "/files/hello.txt")
		self.assertEqual(_("Home/Test_Folder_Copy"), file.folder)

	def execute_test_non_parent_folder(self):
		d = frappe.get_doc({
			"doctype": "File",
			"file_name": _("Test_Folder"),
			"is_folder": 1
		})
		self.assertRaises(frappe.ValidationError, d.save)
