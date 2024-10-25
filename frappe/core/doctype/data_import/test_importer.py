# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.core.doctype.data_import.importer import Importer
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.tests.test_query_builder import db_type_is, run_only_if
from frappe.utils import format_duration, getdate

doctype_name = "DocType for Import"


class UnitTestDataImport(UnitTestCase):
	"""
	Unit tests for DataImport.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestImporter(IntegrationTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		create_doctype_if_not_exists(
			doctype_name,
		)

	def test_data_import_from_file(self) -> None:
		import_file = get_import_file("sample_import_file")
		data_import = self.get_importer(doctype_name, import_file)
		data_import.start_import()

		doc1 = frappe.get_doc(doctype_name, "Test")
		doc2 = frappe.get_doc(doctype_name, "Test 2")
		doc3 = frappe.get_doc(doctype_name, "Test 3")

		self.assertEqual(doc1.description, "test description")
		self.assertEqual(doc1.number, 1)
		self.assertEqual(format_duration(doc1.duration), "3h")

		self.assertEqual(doc1.table_field_1[0].child_title, "child title")
		self.assertEqual(doc1.table_field_1[0].child_description, "child description")

		self.assertEqual(doc1.table_field_1[1].child_title, "child title 2")
		self.assertEqual(doc1.table_field_1[1].child_description, "child description 2")

		self.assertEqual(doc1.table_field_2[1].child_2_title, "title child")
		self.assertEqual(doc1.table_field_2[1].child_2_date, getdate("2019-10-30"))
		self.assertEqual(doc1.table_field_2[1].child_2_another_number, 5)

		self.assertEqual(doc1.table_field_1_again[0].child_title, "child title again")
		self.assertEqual(doc1.table_field_1_again[1].child_title, "child title again 2")
		self.assertEqual(doc1.table_field_1_again[1].child_date, getdate("2021-09-22"))

		self.assertEqual(doc2.description, "test description 2")
		self.assertEqual(format_duration(doc2.duration), "4d 3h")

		self.assertEqual(doc3.another_number, 5)
		self.assertEqual(format_duration(doc3.duration), "5d 5h 45m")

	def test_data_validation_semicolon_success(self) -> None:
		import_file = get_import_file("sample_import_file_semicolon")
		data_import = self.get_importer(doctype_name, import_file, update=True)

		doc = data_import.get_preview_from_template().get("data", [{}])

		self.assertEqual(doc[0][7], "child description with ,comma and")
		# Column count should be 14 (+1 ID)
		self.assertEqual(len(doc[0]), 15)

	def test_data_validation_semicolon_failure(self) -> None:
		import_file = get_import_file("sample_import_file_semicolon")

		data_import = self.get_importer_semicolon(doctype_name, import_file)
		doc = data_import.get_preview_from_template().get("data", [{}])
		# if semicolon delimiter detection fails, and falls back to comma,
		# column number will be less than 15 -> 2 (+1 id)
		self.assertLessEqual(len(doc[0]), 15)

	def test_data_import_preview(self) -> None:
		import_file = get_import_file("sample_import_file")
		data_import = self.get_importer(doctype_name, import_file)
		preview = data_import.get_preview_from_template()

		self.assertEqual(len(preview.data), 4)
		self.assertEqual(len(preview.columns), 16)

	# ignored on postgres because myisam doesn't exist on pg
	@run_only_if(db_type_is.MARIADB)
	def test_data_import_without_mandatory_values(self) -> None:
		import_file = get_import_file("sample_import_file_without_mandatory")
		data_import = self.get_importer(doctype_name, import_file)
		frappe.clear_messages()
		data_import.start_import()
		data_import.reload()

		import_log = frappe.get_all(
			"Data Import Log",
			fields=["row_indexes", "success", "messages", "exception", "docname"],
			filters={"data_import": data_import.name},
			order_by="log_index",
		)

		self.assertEqual(frappe.parse_json(import_log[0]["row_indexes"]), [2, 3])
		expected_error = (
			"Error: <strong>Child 1 of DocType for Import</strong> Row #1: Value missing for: Child Title"
		)
		self.assertEqual(
			frappe.parse_json(frappe.parse_json(import_log[0]["messages"])[0])["message"], expected_error
		)
		expected_error = (
			"Error: <strong>Child 1 of DocType for Import</strong> Row #2: Value missing for: Child Title"
		)
		self.assertEqual(
			frappe.parse_json(frappe.parse_json(import_log[0]["messages"])[1])["message"], expected_error
		)

		self.assertEqual(frappe.parse_json(import_log[1]["row_indexes"]), [4])
		self.assertEqual(
			frappe.parse_json(frappe.parse_json(import_log[1]["messages"])[0])["message"],
			"Title is required",
		)

	def test_data_import_update(self) -> None:
		existing_doc = frappe.get_doc(
			doctype=doctype_name,
			title=frappe.generate_hash(length=8),
			table_field_1=[{"child_title": "child title to update"}],
		)
		existing_doc.save()
		frappe.db.commit()

		import_file = get_import_file("sample_import_file_for_update")
		data_import = self.get_importer(doctype_name, import_file, update=True)
		i = Importer(data_import.reference_doctype, data_import=data_import)

		# update child table id in template date
		i.import_file.raw_data[1][4] = existing_doc.table_field_1[0].name

		# uppercase to check if autoname field isn't replaced in mariadb
		if frappe.db.db_type == "mariadb":
			i.import_file.raw_data[1][0] = existing_doc.name.upper()
		else:
			i.import_file.raw_data[1][0] = existing_doc.name

		i.import_file.parse_data_from_template()
		i.import_data()

		updated_doc = frappe.get_doc(doctype_name, existing_doc.name)
		self.assertEqual(existing_doc.title, updated_doc.title)
		self.assertEqual(updated_doc.description, "test description")
		self.assertEqual(updated_doc.table_field_1[0].child_title, "child title")
		self.assertEqual(updated_doc.table_field_1[0].name, existing_doc.table_field_1[0].name)
		self.assertEqual(updated_doc.table_field_1[0].child_description, "child description")
		self.assertEqual(updated_doc.table_field_1_again[0].child_title, "child title again")

	def get_importer(self, doctype, import_file, update: bool = False):
		data_import = frappe.new_doc("Data Import")
		data_import.import_type = "Insert New Records" if not update else "Update Existing Records"
		data_import.reference_doctype = doctype
		data_import.import_file = import_file.file_url
		data_import.insert()
		# Commit so that the first import failure does not rollback the Data Import insert.
		frappe.db.commit()

		return data_import

	def get_importer_semicolon(self, doctype, import_file, update: bool = False):
		data_import = frappe.new_doc("Data Import")
		data_import.import_type = "Insert New Records" if not update else "Update Existing Records"
		data_import.reference_doctype = doctype
		data_import.import_file = import_file.file_url
		# deliberately overwrite default delimiter options here, causing to fail when parsing `;`
		data_import.delimiter_options = ","
		data_import.insert()
		frappe.db.commit()  # nosemgrep

		return data_import


def create_doctype_if_not_exists(doctype_name, force: bool = False) -> None:
	if force:
		frappe.delete_doc_if_exists("DocType", doctype_name)
		frappe.delete_doc_if_exists("DocType", "Child 1 of " + doctype_name)
		frappe.delete_doc_if_exists("DocType", "Child 2 of " + doctype_name)

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
				{"label": "Child Description", "fieldname": "child_description", "fieldtype": "Small Text"},
				{"label": "Child Date", "fieldname": "child_date", "fieldtype": "Date"},
				{"label": "Child Number", "fieldname": "child_number", "fieldtype": "Int"},
				{"label": "Child Number", "fieldname": "child_another_number", "fieldtype": "Int"},
			],
		}
	).insert()

	# Child Table 2
	table_2_name = "Child 2 of " + doctype_name
	frappe.get_doc(
		{
			"doctype": "DocType",
			"name": table_2_name,
			"module": "Custom",
			"custom": 1,
			"istable": 1,
			"fields": [
				{"label": "Child 2 Title", "fieldname": "child_2_title", "reqd": 1, "fieldtype": "Data"},
				{
					"label": "Child 2 Description",
					"fieldname": "child_2_description",
					"fieldtype": "Small Text",
				},
				{"label": "Child 2 Date", "fieldname": "child_2_date", "fieldtype": "Date"},
				{"label": "Child 2 Number", "fieldname": "child_2_number", "fieldtype": "Int"},
				{"label": "Child 2 Number", "fieldname": "child_2_another_number", "fieldtype": "Int"},
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
				{"label": "Description", "fieldname": "description", "fieldtype": "Small Text"},
				{"label": "Date", "fieldname": "date", "fieldtype": "Date"},
				{"label": "Duration", "fieldname": "duration", "fieldtype": "Duration"},
				{"label": "Number", "fieldname": "number", "fieldtype": "Int"},
				{"label": "Number", "fieldname": "another_number", "fieldtype": "Int"},
				{
					"label": "Table Field 1",
					"fieldname": "table_field_1",
					"fieldtype": "Table",
					"options": table_1_name,
				},
				{
					"label": "Table Field 2",
					"fieldname": "table_field_2",
					"fieldtype": "Table",
					"options": table_2_name,
				},
				{
					"label": "Table Field 1 Again",
					"fieldname": "table_field_1_again",
					"fieldtype": "Table",
					"options": table_1_name,
				},
			],
			"permissions": [{"role": "System Manager"}],
		}
	).insert()


def get_import_file(csv_file_name, force: bool = False):
	file_name = csv_file_name + ".csv"
	_file = frappe.db.exists("File", {"file_name": file_name})
	if force and _file:
		frappe.delete_doc_if_exists("File", _file)

	if frappe.db.exists("File", {"file_name": file_name}):
		f = frappe.get_doc("File", {"file_name": file_name})
	else:
		full_path = get_csv_file_path(file_name)
		f = frappe.get_doc(
			doctype="File", content=frappe.read_file(full_path), file_name=file_name, is_private=1
		)
		f.save(ignore_permissions=True)

	return f


def get_csv_file_path(file_name):
	return frappe.get_app_path("frappe", "core", "doctype", "data_import", "fixtures", file_name)
