# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.core.doctype.data_import.exporter import Exporter
from frappe.core.doctype.data_import.test_importer import create_doctype_if_not_exists
from frappe.core.page.permission_manager.permission_manager import add, reset, update
from frappe.tests import IntegrationTestCase

doctype_name = "DocType for Export"


class TestExporter(IntegrationTestCase):
	def setUp(self):
		create_doctype_if_not_exists(doctype_name)

	def test_exports_specified_fields(self):
		if not frappe.db.exists(doctype_name, "Test"):
			doc = frappe.get_doc(
				doctype=doctype_name,
				title="Test",
				description="Test Description",
				table_field_1=[
					{"child_title": "Child Title 1", "child_description": "Child Description 1"},
					{"child_title": "Child Title 2", "child_description": "Child Description 2"},
				],
				table_field_2=[
					{"child_2_title": "Child Title 1", "child_2_description": "Child Description 1"},
				],
				table_field_1_again=[
					{
						"child_title": "Child Title 1 Again",
						"child_description": "Child Description 1 Again",
					},
				],
			).insert()
		else:
			doc = frappe.get_doc(doctype_name, "Test")

		e = Exporter(
			doctype_name,
			export_fields={
				doctype_name: ["title", "description", "number", "another_number"],
				"table_field_1": ["name", "child_title", "child_description"],
				"table_field_2": ["child_2_date", "child_2_number"],
				"table_field_1_again": [
					"child_title",
					"child_date",
					"child_number",
					"child_another_number",
				],
			},
			export_data=True,
		)
		csv_array = e.get_csv_array()
		header_row = csv_array[0]

		self.assertEqual(
			header_row,
			[
				"Title",
				"Description",
				"Number",
				"another_number",
				"ID (Table Field 1)",
				"Child Title (Table Field 1)",
				"Child Description (Table Field 1)",
				"Child 2 Date (Table Field 2)",
				"Child 2 Number (Table Field 2)",
				"Child Title (Table Field 1 Again)",
				"Child Date (Table Field 1 Again)",
				"Child Number (Table Field 1 Again)",
				"table_field_1_again.child_another_number",
			],
		)

		table_field_1_row_1_name = doc.table_field_1[0].name
		table_field_1_row_2_name = doc.table_field_1[1].name
		# fmt: off
		self.assertEqual(
			csv_array[1],
			["Test", "Test Description", 0, 0, table_field_1_row_1_name, "Child Title 1", "Child Description 1", None, 0, "Child Title 1 Again", None, 0, 0]
		)
		self.assertEqual(
			csv_array[2],
			["", "", "", "", table_field_1_row_2_name, "Child Title 2", "Child Description 2", "", "", "", "", "", ""],
		)
		# fmt: on
		self.assertEqual(len(csv_array), 3)

	def test_export_csv_response(self):
		e = Exporter(
			doctype_name,
			export_fields={doctype_name: ["title", "description"]},
			export_data=True,
			file_type="CSV",
		)
		e.build_response()

		self.assertTrue(frappe.response["result"])
		self.assertEqual(frappe.response["doctype"], doctype_name)
		self.assertEqual(frappe.response["type"], "csv")

	def test_export_respects_child_field_permissions(self):
		child_doctype = f"Child 1 of {doctype_name}"
		test_doc = "_Test Permission Export"
		frappe.delete_doc_if_exists(doctype_name, test_doc)
		self.addCleanup(frappe.delete_doc_if_exists, doctype_name, test_doc)
		self.addCleanup(reset, doctype_name)
		self.addCleanup(frappe.clear_cache, doctype=child_doctype)
		self.addCleanup(
			frappe.db.set_value,
			"DocField",
			{"parent": child_doctype, "fieldname": "child_description"},
			"permlevel",
			0,
		)
		frappe.db.set_value(
			"DocField",
			{"parent": child_doctype, "fieldname": "child_description"},
			"permlevel",
			1,
		)
		add(doctype_name, "All", 0)
		update(doctype_name, "All", 0, "read", 1)
		update(doctype_name, "All", 0, "export", 1)
		frappe.clear_cache(doctype=doctype_name)
		frappe.clear_cache(doctype=child_doctype)

		frappe.get_doc(
			doctype=doctype_name,
			title=test_doc,
			table_field_1=[{"child_title": "Visible Value", "child_description": "Restricted Value"}],
		).insert()

		with self.set_user("test@example.com"):
			exporter = Exporter(
				doctype_name,
				export_fields={
					doctype_name: ["title"],
					"table_field_1": ["child_title", "child_description"],
				},
				export_data=True,
			)

		export = exporter.get_csv_array()
		self.assertIn("Child Title (Table Field 1)", export[0])
		self.assertNotIn("Child Description (Table Field 1)", export[0])
		self.assertNotIn("Restricted Value", str(export))
