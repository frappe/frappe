# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.core.doctype.data_import.importer import Importer, build_fields_dict_for_column_matching
from frappe.tests.test_query_builder import db_type_is, run_only_if
from frappe.tests.utils import FrappeTestCase
from frappe.utils import format_duration, getdate

doctype_name = "DocType for Import"


class TestImporter(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_doctype_if_not_exists(
			doctype_name,
		)

	def test_data_import_from_file(self):
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

	def test_data_import_preview(self):
		import_file = get_import_file("sample_import_file")
		data_import = self.get_importer(doctype_name, import_file)
		preview = data_import.get_preview_from_template()

		self.assertEqual(len(preview.data), 4)
		self.assertEqual(len(preview.columns), 16)

	# ignored on postgres because myisam doesn't exist on pg
	@run_only_if(db_type_is.MARIADB)
	def test_data_import_without_mandatory_values(self):
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

	def test_data_import_update(self):
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

	def get_importer(self, doctype, import_file, update=False):
		data_import = frappe.new_doc("Data Import")
		data_import.import_type = "Insert New Records" if not update else "Update Existing Records"
		data_import.reference_doctype = doctype
		data_import.import_file = import_file.file_url
		data_import.insert()
		# Commit so that the first import failure does not rollback the Data Import insert.
		frappe.db.commit()

<<<<<<< HEAD
		return data_import
=======
		self.assertEqual(len(data_import.value_mappings), 1)
		self.assertEqual(data_import.value_mappings[0].fieldname, "status")
		self.assertEqual(data_import.value_mappings[0].source_value, "Opn")

	def test_create_field_only_for_records_named_by_one_field(self):
		from frappe.core.doctype.data_import.value_mapping import get_create_field

		self.assertEqual(get_create_field("Gender"), "gender")
		self.assertIsNone(get_create_field("User"))

	def test_create_new_mapping_counts_as_mapped(self):
		from frappe.core.doctype.data_import.value_mapping import build_lookup_from_mappings

		row = {
			"reference_doctype": "Contact",
			"fieldname": "gender",
			"source_value": " Zorblax ",
			"target_value": "",
			"create_new": 1,
			"can_create": 1,
		}
		self.assertEqual(build_lookup_from_mappings([row]), {"Contact.gender": {"Zorblax": "Zorblax"}})
		self.assertEqual(build_lookup_from_mappings([{**row, "can_create": 0}]), {})

	def test_create_field_needs_create_permission(self):
		from frappe.core.doctype.data_import.value_mapping import get_create_field

		with self.set_user(self._user_without_gender_create()):
			self.assertIsNone(get_create_field("Gender"))
		with self.set_user("test@example.com"):
			self.assertEqual(get_create_field("Gender"), "gender")

	def test_import_creates_missing_link_records_marked_create_new(self):
		gender = "Data Import Test Gender"
		data_import = self._contact_import_creating_gender(gender, "Zed Create Test")

		data_import.start_import()
		contact = frappe.db.get_value("Contact", {"first_name": "Zed Create Test"}, ["name", "gender"])
		if contact:
			self.addCleanup(_delete_doctype_records, "Contact", [contact[0]])
		self.assertEqual(data_import.reload().status, "Success")
		self.assertTrue(frappe.db.exists("Gender", gender))
		self.assertEqual(contact[1], gender)

	def test_import_does_not_create_link_records_for_skipped_rows(self):
		gender = "Data Import Test Gender Skipped"
		data_import = self._contact_import_creating_gender(gender, "Zed Skipped Test")
		data_import.append("skipped_rows", {"row_number": 2, "row_data": "[]"})
		data_import.save()
		frappe.db.commit()  # nosemgrep

		data_import.start_import()
		self.assertFalse(frappe.db.exists("Gender", gender))
		self.assertFalse(frappe.db.exists("Contact", {"first_name": "Zed Skipped Test"}))

	def test_user_with_create_permission_creates_missing_link_records(self):
		gender = "Data Import Test Gender Allowed"
		data_import = self._contact_import_creating_gender(gender, "Zed Allowed Test")

		with self.set_user("test@example.com"):
			data_import.start_import()
		contact = frappe.db.get_value("Contact", {"first_name": "Zed Allowed Test"}, ["name", "gender"])
		if contact:
			self.addCleanup(_delete_doctype_records, "Contact", [contact[0]])
		self.assertEqual(data_import.reload().status, "Success")
		self.assertEqual(frappe.db.get_value("Gender", gender, "owner"), "test@example.com")
		self.assertEqual(contact[1], gender)

	def test_user_without_create_permission_gets_the_link_error(self):
		gender = "Data Import Test Gender Denied"
		data_import = self._contact_import_creating_gender(gender, "Zed Denied Test")

		with self.set_user(self._user_without_gender_create()):
			data_import.start_import()
		self.assertEqual(data_import.reload().status, "Error")
		self.assertFalse(frappe.db.exists("Gender", gender))
		self.assertFalse(frappe.db.exists("Contact", {"first_name": "Zed Denied Test"}))
		log = frappe.get_all(
			"Data Import Log",
			fields=["success", "messages"],
			filters={"data_import": data_import.name},
		)
		self.assertEqual(len(log), 1)
		self.assertFalse(log[0].success)
		messages = [frappe.parse_json(m)["message"] for m in frappe.parse_json(log[0].messages)]
		self.assertIn(f"Could not find Gender: {gender}", messages)

	def _contact_import_creating_gender(self, gender, first_name):
		"""A saved Contact import whose missing Gender is marked to be created when the import runs."""
		self.addCleanup(_delete_doctype_records, "Gender", [gender])
		import_file = frappe.get_doc(
			doctype="File",
			content=f"First Name,Gender\n{first_name},{gender}\n",
			file_name="data_import_create_gender.csv",
			is_private=1,
		)
		import_file.save(ignore_permissions=True)
		_register_file_cleanup(self, import_file)

		data_import = self.get_importer("Contact", import_file)
		mapping = data_import.value_mappings[0]
		self.assertEqual((mapping.fieldname, mapping.can_create, mapping.create_new), ("gender", 1, 0))

		mapping.create_new = 1
		data_import.save()
		self.assertEqual(data_import.value_mappings[0].create_new, 1)
		frappe.db.commit()  # nosemgrep
		return data_import

	def _user_without_gender_create(self):
		"""Can create Contacts but not Genders."""
		email = "data-import-sales-user@example.com"
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Data Import Sales User",
					"send_welcome_email": 0,
					"roles": [{"role": "Sales User"}],
				}
			).insert(ignore_permissions=True)
			frappe.db.commit()  # nosemgrep
			self.addCleanup(_delete_doctype_records, "User", [email])
		return email

	def _contact_import_with_late_bad_row(self):
		rows = [f"Late Row Test {i},Open" for i in range(12)] + ["Late Row Zed,Open,extra"]
		import_file = frappe.get_doc(
			doctype="File",
			content="First Name,Status\n" + "\n".join(rows) + "\n",
			file_name="data_import_late_bad_row.csv",
			is_private=1,
		)
		import_file.save(ignore_permissions=True)
		_register_file_cleanup(self, import_file)
		return self.get_importer("Contact", import_file)

	def test_preview_carries_warned_rows_past_the_preview(self):
		data_import = self._contact_import_with_late_bad_row()
		out = Importer("Contact", data_import=data_import).get_data_for_import_preview()

		self.assertTrue(out.max_rows_exceeded)
		self.assertIn(14, [w.get("row") for w in out.warnings])
		self.assertEqual([row[0] for row in out.warning_rows], [14])
		self.assertEqual(out.warning_rows[0][1], "Late Row Zed")

	def test_skipped_rows_export_reads_cells_from_the_file(self):
		data_import = self._contact_import_with_late_bad_row()
		data_import.append("skipped_rows", {"row_number": 14, "row_data": "[]"})
		data_import.save()

		Importer("Contact", data_import=data_import).export_skipped_rows()
		self.assertIn("Late Row Zed", frappe.response["result"])

	def test_source_value_strip_applied_during_import_resolve(self):
		from frappe.core.doctype.data_import.value_mapping import (
			build_lookup_from_mappings,
			resolve_import_value,
		)

		lookup = build_lookup_from_mappings(
			[
				{
					"reference_doctype": "Contact",
					"fieldname": "status",
					"source_value": "Pasiv",
					"target_value": "Passive",
				}
			]
		)
		df = frappe._dict(fieldname="status", parent="Contact")
		self.assertEqual(resolve_import_value(" Pasiv ", df, "Contact", lookup), "Passive")

	def test_row_count_label_returns_row_count(self):
		from frappe.core.doctype.data_import.value_mapping import row_count_label

		self.assertEqual(row_count_label([]), "")
		self.assertEqual(row_count_label([3]), "1")
		self.assertEqual(row_count_label([2, 3, 4]), "3")

	def test_format_row_numbers_for_warning_truncates_long_lists(self):
		from frappe.core.doctype.data_import.importer import format_row_numbers_for_warning

		self.assertEqual(format_row_numbers_for_warning([2, 3, 4]), "2, 3, 4")
		self.assertEqual(
			format_row_numbers_for_warning([2, 3, 4, 5, 6, 7, 8, 9, 100]),
			"2, 3, 4, 5, 6, 7, ... 100",
		)

	def test_get_value_row_map_groups_rows_by_value(self):
		from frappe.core.doctype.data_import.importer import get_value_row_map

		value_rows = get_value_row_map(["Open", "Closed", None, "Open", 5, "Open"], [4, 2, 3, 2, 6, 4])
		self.assertEqual(value_rows, {"Open": [2, 4], "Closed": [2], "5": [6]})
		self.assertEqual(list(value_rows), ["Open", "Closed", "5"])

	def test_link_validation_ignores_header_row_when_not_on_first_line(self):
		"""Leading blank rows must not treat the header line as data (e.g. Gender → row 3)."""
		from frappe.core.doctype.data_import.importer import ImportFile
		from frappe.core.doctype.data_import.value_mapping import get_column_invalid_items

		for gender in ("Male", "Female"):
			if not frappe.db.exists("Gender", gender):
				frappe.get_doc({"doctype": "Gender", "gender": gender}).insert()

		csv_content = (
			"\n"
			"First Name,Last Name,Status,Salutation,Gender\n"
			"Alice,Smith,Opn,Mr.,Female\n"
			"Bob,Jones,Pasiv,Mrs,Male\n"
		)
		import_file = frappe.get_doc(
			doctype="File",
			content=csv_content,
			file_name="data_import_leading_blank_row.csv",
			is_private=1,
		)
		import_file.save(ignore_permissions=True)

		imp = ImportFile("Contact", import_file.file_url, import_type=INSERT)
		gender_col = next(c for c in imp.columns if c.df and c.df.fieldname == "gender")
		invalid_sources = {item["source"] for item in get_column_invalid_items(gender_col)}

		self.assertNotIn("Gender", invalid_sources)

	def test_link_and_select_warnings_include_row_numbers(self):
		"""Column warnings for Link/Select list invalid values with 1-based sheet row numbers."""
		if not frappe.db.exists("Salutation", "Mr"):
			frappe.get_doc({"doctype": "Salutation", "salutation": "Mr"}).insert()
		for name in ("Miss", "Ms"):
			if frappe.db.exists("Salutation", name):
				frappe.delete_doc("Salutation", name)

		link_msg = Column(
			0, "Salutation", "Contact", ["Mr.", "Mr.", "Miss"], value_row_numbers=[2, 3, 4]
		).warnings[0]["message"]
		self.assertIn("Mr.", link_msg)
		self.assertIn("is not a valid", link_msg)
		self.assertIn("rows 2, 3", link_msg)
		self.assertIn("Miss", link_msg)
		self.assertIn("row 4", link_msg)

		select_msg = Column(
			5, "Status", "Contact", ["Opn", "Pasiv", "Open"], value_row_numbers=[2, 3, 4]
		).warnings[0]["message"]
		self.assertIn("Opn", select_msg)
		self.assertIn("is not valid", select_msg)
		self.assertIn("row 2", select_msg)
		self.assertIn("Pasiv", select_msg)
		self.assertIn("row 3", select_msg)
		self.assertIn("Allowed:", select_msg)
>>>>>>> 6ce268a (feat(data-import): let an import create missing link records)

	def test_data_import_without_label(self):
		"""Test fallback to fieldname when label is not set for a table."""

		meta = frappe.get_meta(doctype_name)
		table_field = meta.get_field("table_field_1")
		original_label = table_field.label
		table_field.label = None
		fields_dict = build_fields_dict_for_column_matching(doctype_name)
		expected_key = "Child Title (table_field_1)"
		self.assertIn(
			expected_key, fields_dict, f"Fallback failed: '{expected_key}' not found in mapping dict"
		)
		expected_id_key = "ID (table_field_1)"
		self.assertIn(expected_id_key, fields_dict, "ID fallback failed")
		table_field.label = original_label  # maintain sanity in test env


def create_doctype_if_not_exists(doctype_name, force=False):
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
			"allow_import": 1,
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
			"permissions": [{"role": "System Manager", "import": 1}],
		}
	).insert()


def get_import_file(csv_file_name, force=False):
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
