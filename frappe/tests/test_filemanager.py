# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe
import os
import unittest

from frappe.core.doctype.file.file import get_file, get_files_path

test_content1 = 'Hello'
test_content2 = 'Hello World'

def make_test_doc():
	d = frappe.new_doc('ToDo')
	d.description = 'Test'
	d.save()
	return d.doctype, d.name

class TestSimpleFile(unittest.TestCase):

	def setUp(self):
		self.attached_to_doctype, self.attached_to_docname = make_test_doc()
		self.test_content = test_content1
		_file = frappe.get_doc("File", {"file_name": "hello.txt", "content": self.test_content,
			"attached_to_doctype": self.attached_to_doctype, "attached_to_docname": self.attached_to_docname})
		self.saved_file = _file.save_file()
		self.saved_filename = get_files_path(self.saved_file.file_name)
		
	def test_save(self):
		filename, content = get_file(self.saved_file.name)
		self.assertEqual(content, self.test_content)

	def tearDown(self):
		# File gets deleted on rollback, so blank
		pass


class TestSameFileName(unittest.TestCase):

	def setUp(self):
		self.attached_to_doctype, self.attached_to_docname = make_test_doc()
		self.test_content1 = test_content1
		self.test_content2 = test_content2
		_file1 = frappe.get_doc("File", {"file_name": "hello.txt", "content": self.test_content1,
			"attached_to_doctype": self.attached_to_doctype, "attached_to_docname": self.attached_to_docname})
		_file2 = frappe.get_doc("File", {"file_name": "hello.txt", "content": self.test_content2,
			"attached_to_doctype": self.attached_to_doctype, "attached_to_docname": self.attached_to_docname})
		self.saved_file1 = _file1.save_file()
		self.saved_file2 = _file2.save_file()
		self.saved_filename1 = get_files_path(self.saved_file1.file_name)
		self.saved_filename2 = get_files_path(self.saved_file2.file_name)
	
	def test_saved_content(self):
		filename1, content1 = get_file(self.saved_file1.name)
		self.assertEqual(content1, self.test_content1)
		filename2, content2 = get_file(self.saved_file2.name)
		self.assertEqual(content2, self.test_content2)

	def tearDown(self):
		# File gets deleted on rollback, so blank
		pass


class TestSameContent(unittest.TestCase):

	def setUp(self):
		self.attached_to_doctype1, self.attached_to_docname1 = make_test_doc()
		self.attached_to_doctype2, self.attached_to_docname2 = make_test_doc()
		self.test_content1 = test_content1
		self.test_content2 = test_content1
		self.orig_filename = 'hello.txt'
		self.dup_filename = 'hello2.txt'
		_file1 = frappe.get_doc("File", {"file_name": self.orig_filename, "content": self.test_content1,
			"attached_to_doctype": self.attached_to_doctype1, "attached_to_docname": self.attached_to_docname1})
		_file2 = frappe.get_doc("File", {"file_name": self.dup_filename, "content": self.test_content2,
			"attached_to_doctype": self.attached_to_doctype2, "attached_to_docname": self.attached_to_docname2})
		self.saved_file1 = _file1.save_file()
		self.saved_file2 = _file2.save_file()
		self.saved_filename1 = get_files_path(self.saved_file1.file_name)
		self.saved_filename2 = get_files_path(self.saved_file2.file_name)
	
	def test_saved_content(self):
		filename1, content1 = get_file(self.saved_file1.name)
		filename2, content2 = get_file(self.saved_file2.name)
		self.assertEqual(filename1, filename2)
		self.assertFalse(os.path.exists(get_files_path(self.dup_filename)))

	def tearDown(self):
		# File gets deleted on rollback, so blank
		pass
