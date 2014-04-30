# Copyright (c) 2014, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe, unittest
from frappe.core.page.data_import_tool import exporter
from frappe.core.page.data_import_tool import importer
from frappe.utils.datautils import read_csv_content

class TestDataImport(unittest.TestCase):
	def test_export(self):
		exporter.get_template("User", all_doctypes="No", with_data="No")
		content = read_csv_content(frappe.response.result)
		self.assertTrue(content[1][1], "User")

	def test_export_with_data(self):
		exporter.get_template("User", all_doctypes="No", with_data="Yes")
		content = read_csv_content(frappe.response.result)
		self.assertTrue(content[1][1], "User")
		self.assertTrue("Administrator" in [c[1] for c in content if len(c)>1])

	def test_export_with_all_doctypes(self):
		exporter.get_template("User", all_doctypes="Yes", with_data="Yes")
		content = read_csv_content(frappe.response.result)
		self.assertTrue(content[1][1], "User")
		self.assertTrue('"Administrator"' in [c[1] for c in content if len(c)>1])
		self.assertEquals(content[13][0], "DocType:")
		self.assertEquals(content[13][1], "User")
		self.assertTrue("UserRole" in content[13])

	def test_import(self):
		if frappe.db.exists("Blog Category", "test-category"):
			frappe.delete_doc("Blog Category", "test-category")

		exporter.get_template("Blog Category", all_doctypes="No", with_data="No")
		content = read_csv_content(frappe.response.result)
		content.append(["", "", "test-category", "Test Cateogry"])
		importer.upload(content)
		self.assertTrue(frappe.db.get_value("Blog Category", "test-category", "title"), "Test Category")

		# export with data
		exporter.get_template("Blog Category", all_doctypes="No", with_data="Yes")
		content = read_csv_content(frappe.response.result)

		# overwrite
		content[-1][3] = "New Title"
		importer.upload(content, overwrite=True)
		self.assertTrue(frappe.db.get_value("Blog Category", "test-category", "title"), "New Title")

	def test_import_with_children(self):
		exporter.get_template("Event", all_doctypes="Yes", with_data="No")
		content = read_csv_content(frappe.response.result)
		content.append([""] * len(content[-2]))
		content[-1][2] = "__Test Event"
		content[-1][3] = "Private"
		content[-1][3] = "2014-01-01 10:00:00.000000"
		content[-1][content[15].index("person")] = "Administrator"
		importer.upload(content)

		ev = frappe.get_doc("Event", {"subject":"__Test Event"})
		self.assertTrue("Administrator" in [d.person for d in ev.event_individuals])
