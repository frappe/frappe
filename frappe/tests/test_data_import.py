# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe, unittest
from frappe.core.page.data_import_tool import exporter
from frappe.core.page.data_import_tool import importer
from frappe.utils.csvutils import read_csv_content

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

	def test_import_only_children(self):
		user_email = "test_import_userrole@example.com"
		if frappe.db.exists("User", user_email):
			frappe.delete_doc("User", user_email)

		frappe.get_doc({"doctype": "User", "email": user_email, "first_name": "Test Import UserRole"}).insert()

		exporter.get_template("UserRole", "User", all_doctypes="No", with_data="No")
		content = read_csv_content(frappe.response.result)
		content.append(["", "test_import_userrole@example.com", "Blogger"])
		importer.upload(content)

		user = frappe.get_doc("User", user_email)
		self.assertEquals(len(user.get("user_roles")), 1)
		self.assertTrue(user.get("user_roles")[0].role, "Blogger")

		# overwrite
		exporter.get_template("UserRole", "User", all_doctypes="No", with_data="No")
		content = read_csv_content(frappe.response.result)
		content.append(["", "test_import_userrole@example.com", "Website Manager"])
		importer.upload(content, overwrite=True)

		user = frappe.get_doc("User", user_email)
		self.assertEquals(len(user.get("user_roles")), 1)
		self.assertTrue(user.get("user_roles")[0].role, "Website Manager")

	def test_import_with_children(self):
		exporter.get_template("Event", all_doctypes="Yes", with_data="No")
		content = read_csv_content(frappe.response.result)

		content.append([None] * len(content[-2]))
		content[-1][2] = "__Test Event with children"
		content[-1][3] = "Private"
		content[-1][4] = "2014-01-01 10:00:00.000000"
		content[-1][content[15].index("role")] = "System Manager"
		importer.upload(content)

		ev = frappe.get_doc("Event", {"subject":"__Test Event with children"})
		self.assertTrue("System Manager" in [d.role for d in ev.roles])
