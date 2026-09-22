# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.core.doctype.data_export.exporter import DataExporter
from frappe.tests import IntegrationTestCase


class TestDataExporter(IntegrationTestCase):
	def setUp(self):
		self.doctype_name = "Test DocType for Export Tool"
		self.doc_name = "Test Data for Export Tool"
		self.create_doctype_if_not_exists(doctype_name=self.doctype_name)
		self.create_test_data()

	def create_doctype_if_not_exists(self, doctype_name, force=False):
		"""
		Helper Function for setting up doctypes
		"""
		if force:
			frappe.delete_doc_if_exists("DocType", doctype_name)
			frappe.delete_doc_if_exists("DocType", "Child 1 of " + doctype_name)

		if frappe.db.exists("DocType", doctype_name):
			return

		# Child Table 1
		table_1_name = "Child 1 of " + doctype_name
		frappe.get_doc(
			{
				"doctype": "DocType",
				"name": table_1_name,
				"module": "Custom",
				"custom": 1,
				"istable": 1,
				"fields": [
					{"label": "Child Title", "fieldname": "child_title", "reqd": 1, "fieldtype": "Data"},
					{"label": "Child Number", "fieldname": "child_number", "fieldtype": "Int"},
				],
			}
		).insert()

		# Main Table
		frappe.get_doc(
			{
				"doctype": "DocType",
				"name": doctype_name,
				"module": "Custom",
				"custom": 1,
				"autoname": "field:title",
				"fields": [
					{"label": "Title", "fieldname": "title", "reqd": 1, "fieldtype": "Data"},
					{"label": "Number", "fieldname": "number", "fieldtype": "Int"},
					{
						"label": "Table Field 1",
						"fieldname": "table_field_1",
						"fieldtype": "Table",
						"options": table_1_name,
					},
				],
				"permissions": [{"role": "System Manager"}],
			}
		).insert()

	def create_test_data(self, force=False):
		"""
		Helper Function creating test data
		"""
		if force:
			frappe.delete_doc(self.doctype_name, self.doc_name)

		if not frappe.db.exists(self.doctype_name, self.doc_name):
			self.doc = frappe.get_doc(
				doctype=self.doctype_name,
				title=self.doc_name,
				number="100",
				table_field_1=[
					{"child_title": "Child Title 1", "child_number": "50"},
					{"child_title": "Child Title 2", "child_number": "51"},
				],
			).insert()
		else:
			self.doc = frappe.get_doc(self.doctype_name, self.doc_name)

	def test_export_content(self):
		exp = DataExporter(doctype=self.doctype_name, file_type="CSV")
		exp.build_response()

		self.assertEqual(frappe.response["type"], "csv")
		self.assertEqual(frappe.response["doctype"], self.doctype_name)
		self.assertTrue(frappe.response["result"])
		self.assertRegex(frappe.response["result"], r"Child Title 1.*?,50")
		self.assertRegex(frappe.response["result"], r"Child Title 2.*?,51")

	def test_export_type(self):
		for type in ["csv", "Excel"]:
			with self.subTest(type=type):
				exp = DataExporter(doctype=self.doctype_name, file_type=type)
				exp.build_response()

				self.assertEqual(frappe.response["doctype"], self.doctype_name)
				self.assertTrue(frappe.response["result"])

				if type == "csv":
					self.assertEqual(frappe.response["type"], "csv")
				elif type == "Excel":
					self.assertEqual(frappe.response["type"], "binary")
					self.assertEqual(
						frappe.response["filename"], self.doctype_name + ".xlsx"
					)  # 'Test DocType for Export Tool.xlsx')
					self.assertTrue(frappe.response["filecontent"])

	def test_export_with_only_if_creator_permission(self):
		role = frappe.get_doc(doctype="Role", role_name="Test Owner Export", desk_access=1).insert()
		user = frappe.get_doc(
			doctype="User",
			email="test-owner-export@example.com",
			first_name="Test Owner Export",
			send_welcome_email=0,
			roles=[{"role": role.name}],
		).insert()
		frappe.get_doc(
			doctype="Custom DocPerm",
			parent=self.doctype_name,
			role=role.name,
			read=1,
			export=1,
			if_owner=1,
		).insert()

		owned_doc = frappe.get_doc(
			doctype=self.doctype_name,
			title="Test Owner Export Data",
		).insert()
		frappe.db.set_value(self.doctype_name, owned_doc.name, "owner", user.name)
		frappe.clear_cache(doctype=self.doctype_name)

		with self.set_user(user.name):
			exporter = DataExporter(doctype=self.doctype_name, file_type="CSV")
			exporter.build_response()

		self.assertEqual([doc.name for doc in exporter.data], [owned_doc.name])

	def tearDown(self):
		pass
