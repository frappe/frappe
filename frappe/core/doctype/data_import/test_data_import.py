# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe, unittest
from frappe.core.doctype.data_export import exporter
from frappe.core.doctype.data_import import importer
from frappe.utils.csvutils import read_csv_content

class TestDataImport(unittest.TestCase):
	def test_export(self):
		exporter.export_data("User", all_doctypes=True, template=True)
		content = read_csv_content(frappe.response.result)
		self.assertTrue(content[1][1], "User")

	def test_export_with_data(self):
		exporter.export_data("User", all_doctypes=True, template=True, with_data=True)
		content = read_csv_content(frappe.response.result)
		self.assertTrue(content[1][1], "User")
		self.assertTrue('"Administrator"' in [c[1] for c in content if len(c)>1])

	def test_export_with_all_doctypes(self):
		exporter.export_data("User", all_doctypes="Yes", template=True, with_data=True)
		content = read_csv_content(frappe.response.result)
		self.assertTrue(content[1][1], "User")
		self.assertTrue('"Administrator"' in [c[1] for c in content if len(c)>1])
		self.assertEqual(content[13][0], "DocType:")
		self.assertEqual(content[13][1], "User")
		self.assertTrue("Has Role" in content[13])

	def test_import(self):
		if frappe.db.exists("Blog Category", "test-category"):
			frappe.delete_doc("Blog Category", "test-category")

		exporter.export_data("Blog Category", all_doctypes=True, template=True)
		content = read_csv_content(frappe.response.result)
		content.append(["", "test-category", "Test Cateogry"])
		importer.upload(content)
		self.assertTrue(frappe.db.get_value("Blog Category", "test-category", "title"), "Test Category")

		# export with data
		exporter.export_data("Blog Category", all_doctypes=True, template=True, with_data=True)
		content = read_csv_content(frappe.response.result)

		# overwrite
		content[-1][3] = "New Title"
		importer.upload(content, overwrite=True)
		self.assertTrue(frappe.db.get_value("Blog Category", "test-category", "title"), "New Title")

	def test_import_only_children(self):
		user_email = "test_import_userrole@example.com"
		if frappe.db.exists("User", user_email):
			frappe.delete_doc("User", user_email, force=True)

		frappe.get_doc({"doctype": "User", "email": user_email, "first_name": "Test Import UserRole"}).insert()

		exporter.export_data("Has Role", "User", all_doctypes=True, template=True)
		content = read_csv_content(frappe.response.result)
		content.append(["", "test_import_userrole@example.com", "Blogger"])
		importer.upload(content)

		user = frappe.get_doc("User", user_email)
		self.assertTrue(frappe.db.get_value("Has Role", filters={"role": "Blogger", "parent": user_email, "parenttype": "User"}))
		self.assertTrue(user.get("roles")[0].role, "Blogger")

		# overwrite
		exporter.export_data("Has Role", "User", all_doctypes=True, template=True)
		content = read_csv_content(frappe.response.result)
		content.append(["", "test_import_userrole@example.com", "Website Manager"])
		importer.upload(content, overwrite=True)

		user = frappe.get_doc("User", user_email)
		self.assertEqual(len(user.get("roles")), 1)
		self.assertTrue(user.get("roles")[0].role, "Website Manager")

	def test_import_with_children(self):	#pylint: disable=R0201
		if frappe.db.exists("Event", "EV00001"):
			frappe.delete_doc("Event", "EV00001")
		exporter.export_data("Event", all_doctypes="Yes", template=True)
		content = read_csv_content(frappe.response.result)

		content.append([None] * len(content[-2]))
		content[-1][1] = "__Test Event with children"
		content[-1][2] = "Private"
		content[-1][3] = "2014-01-01 10:00:00.000000"
		importer.upload(content)

		frappe.get_doc("Event", {"subject":"__Test Event with children"})

	def test_excel_import(self):
		if frappe.db.exists("Event", "EV00001"):
			frappe.delete_doc("Event", "EV00001")

		exporter.export_data("Event", all_doctypes=True, template=True, file_type="Excel")
		from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file
		content = read_xlsx_file_from_attached_file(fcontent=frappe.response.filecontent)
		content.append(["", "_test", "Private", "05-11-2017 13:51:48", "Event", "blue", "0", "0", "", "Open", "", 0, "", 0, "", "", "1", 0, "", "", 0, 0, 0, 0, 0, 0, 0])
		importer.upload(content)
		self.assertTrue(frappe.db.get_value("Event", {"subject": "_test"}, "name"))