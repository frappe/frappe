# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.core.doctype.data_import.importer import (
	ACTION_INSERT,
	ACTION_UPDATE,
	INSERT,
	UPSERT,
	Column,
	Importer,
	_get_tree_node_key,
	build_fields_dict_for_column_matching,
	get_tree_alias_fieldname,
	uses_tree_alias_references,
)
from frappe.tests import IntegrationTestCase
from frappe.tests.test_query_builder import db_type_is, unimplemented_for
from frappe.utils import cint, format_duration, getdate

doctype_name = "DocType for Import"
SAMPLE_IMPORT_DOC_NAMES = ("Test", "Test 2", "Test 3")


def _delete_data_import(data_import_name):
	"""Remove a persisted Data Import and its logs after integration tests."""
	if not data_import_name or not frappe.db.exists("Data Import", data_import_name):
		return
	frappe.db.delete("Data Import Log", {"data_import": data_import_name})
	frappe.delete_doc("Data Import", data_import_name, force=1, ignore_permissions=True)
	frappe.db.commit()  # nosemgrep


def _delete_file(file_name):
	if not file_name or not frappe.db.exists("File", file_name):
		return
	frappe.delete_doc("File", file_name, force=1, ignore_permissions=True)
	frappe.db.commit()  # nosemgrep


def _delete_doctype_records(doctype, names):
	for name in names:
		if name:
			frappe.delete_doc_if_exists(doctype, name, force=1)
	frappe.db.commit()  # nosemgrep


def _register_data_import_cleanup(test_case, data_import):
	test_case.addCleanup(_delete_data_import, data_import.name)


def _register_file_cleanup(test_case, file_doc):
	test_case.addCleanup(_delete_file, file_doc.name)


class TestImporter(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_doctype_if_not_exists(
			doctype_name,
		)

	def test_data_import_from_file(self):
		self.addCleanup(_delete_doctype_records, doctype_name, SAMPLE_IMPORT_DOC_NAMES)
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

	def test_skip_rows_during_import(self):
		self.addCleanup(_delete_doctype_records, doctype_name, ("Test 2", "Test 3"))
		for name in ("Test", "Test 2", "Test 3"):
			frappe.delete_doc_if_exists(doctype_name, name)
		frappe.db.commit()  # ensure deletions are flushed to DB before import; # nosemgrep

		import_file = get_import_file("sample_import_file")
		data_import = self.get_importer(doctype_name, import_file)
		data_import.append("skipped_rows", {"row_number": 2, "row_data": "[]"})
		data_import.save()
		data_import.start_import()
		data_import.reload()

		self.assertFalse(frappe.db.exists(doctype_name, "Test"))
		self.assertTrue(frappe.db.exists(doctype_name, "Test 2"))
		self.assertTrue(frappe.db.exists(doctype_name, "Test 3"))
		self.assertEqual(data_import.status, "Success")

	def test_data_validation_semicolon_success(self):
		import_file = get_import_file("sample_import_file_semicolon")
		data_import = self.get_importer(doctype_name, import_file, update=True, use_sniffer=True)

		doc = data_import.get_preview_from_template().get("data", [{}])

		self.assertEqual(doc[0][7], "child description with ,comma and")
		# Column count should be 14 (+1 ID)
		self.assertEqual(len(doc[0]), 15)

	def test_custom_delimiter_semicolon_without_sniffer(self):
		import_file = get_import_file("sample_import_file_semicolon")
		data_import = self.get_importer(doctype_name, import_file)
		data_import.custom_delimiters = 1
		data_import.delimiter_options = ";"
		data_import.use_csv_sniffer = 0
		data_import.save()

		preview = data_import.get_preview_from_template()
		self.assertGreater(len(preview.columns), 5)
		self.assertEqual(preview.columns[1].header_title, "Title")

	def test_data_validation_semicolon_failure(self):
		import_file = get_import_file("sample_import_file_semicolon")

		data_import = self.get_importer_semicolon(doctype_name, import_file, use_sniffer=True)
		doc = data_import.get_preview_from_template().get("data", [{}])
		# if semicolon delimiter detection fails, and falls back to comma,
		# column number will be less than 15 -> 2 (+1 id)
		self.assertLessEqual(len(doc[0]), 15)

	def test_data_import_preview(self):
		import_file = get_import_file("sample_import_file")
		data_import = self.get_importer(doctype_name, import_file)
		preview = data_import.get_preview_from_template()

		self.assertEqual(len(preview.data), 4)
		self.assertEqual(len(preview.columns), 16)

	# ignored on postgres because myisam doesn't exist on pg
	@unimplemented_for(db_type_is.POSTGRES, db_type_is.SQLITE)
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
		frappe.db.commit()  # ensure saved document is visible to other DB connections; # nosemgrep
		self.addCleanup(_delete_doctype_records, doctype_name, [existing_doc.name])

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

	def test_data_import_upsert(self):
		existing_doc = frappe.get_doc(
			doctype=doctype_name,
			title=frappe.generate_hash(length=8),
			description="old description",
		)
		existing_doc.insert()
		frappe.db.commit()  # nosemgrep

		new_title = frappe.generate_hash(length=8)
		self.addCleanup(_delete_doctype_records, doctype_name, [existing_doc.name, new_title])

		import_file = get_import_file("sample_import_file_for_update")
		data_import = self.get_importer(doctype_name, import_file, import_type=UPSERT)
		i = Importer(data_import.reference_doctype, data_import=data_import)
		if frappe.db.db_type == "mariadb":
			i.import_file.raw_data[1][0] = existing_doc.name.upper()
		else:
			i.import_file.raw_data[1][0] = existing_doc.name
		i.import_file.raw_data.append(
			[
				new_title,
				"new description",
				1,
				2,
				"",
				"child title",
				"child description",
				"child title",
				"14-08-2019",
				4,
				"child title again",
				"22-09-2020",
				5,
				7,
			]
		)
		i.import_file.parse_data_from_template()
		i.import_data()

		updated_doc = frappe.get_doc(doctype_name, existing_doc.name)
		self.assertEqual(existing_doc.title, updated_doc.title)
		self.assertEqual(updated_doc.description, "test description")

		self.assertTrue(frappe.db.exists(doctype_name, new_title))
		new_doc = frappe.get_doc(doctype_name, new_title)
		self.assertEqual(new_doc.description, "new description")

		import_logs = frappe.get_all(
			"Data Import Log",
			fields=["import_action", "docname", "success"],
			filters={"data_import": data_import.name, "success": 1},
			order_by="log_index",
		)
		self.assertEqual(len(import_logs), 2)
		actions_by_docname = {log.docname: log.import_action for log in import_logs}
		self.assertEqual(actions_by_docname[existing_doc.name], ACTION_UPDATE)
		self.assertEqual(actions_by_docname[new_title], ACTION_INSERT)

	def test_data_import_upsert_unchanged_existing_record(self):
		"""Upsert must succeed when an existing row has no field changes."""
		existing_doc = frappe.get_doc(
			doctype=doctype_name,
			title=frappe.generate_hash(length=8),
			description="test description",
			number=1,
			another_number=2,
		)
		existing_doc.insert()
		frappe.db.commit()  # nosemgrep
		self.addCleanup(_delete_doctype_records, doctype_name, [existing_doc.name])

		import_file = get_import_file("sample_import_file_for_update")
		data_import = self.get_importer(doctype_name, import_file, import_type=UPSERT)
		i = Importer(data_import.reference_doctype, data_import=data_import)
		row = list(i.import_file.raw_data[1])
		row[0] = existing_doc.name.upper() if frappe.db.db_type == "mariadb" else existing_doc.name
		row[1] = existing_doc.title
		i.import_file.raw_data[1] = row
		i.import_file.parse_data_from_template()
		i.import_data()

		import_logs = frappe.get_all(
			"Data Import Log",
			fields=["import_action", "success"],
			filters={"data_import": data_import.name, "success": 1},
		)
		self.assertEqual(len(import_logs), 1)
		self.assertEqual(import_logs[0].import_action, ACTION_UPDATE)

	def test_get_import_status_upsert_counts(self):
		existing_doc = frappe.get_doc(
			doctype=doctype_name,
			title=frappe.generate_hash(length=8),
			description="old description",
		)
		existing_doc.insert()
		frappe.db.commit()  # nosemgrep

		new_title = frappe.generate_hash(length=8)
		self.addCleanup(_delete_doctype_records, doctype_name, [existing_doc.name, new_title])

		import_file = get_import_file("sample_import_file_for_update")
		data_import = self.get_importer(doctype_name, import_file, import_type=UPSERT)
		i = Importer(data_import.reference_doctype, data_import=data_import)
		i.import_file.raw_data[1][0] = existing_doc.name
		i.import_file.raw_data.append(
			[
				new_title,
				"new description",
				1,
				2,
				"",
				"child title",
				"child description",
				"child title",
				"14-08-2019",
				4,
				"child title again",
				"22-09-2020",
				5,
				7,
			]
		)
		i.import_file.parse_data_from_template()
		i.import_data()

		from frappe.core.doctype.data_import.data_import import get_import_status

		status = get_import_status(data_import.name)
		self.assertEqual(status["inserted"], 1)
		self.assertEqual(status["updated"], 1)
		self.assertEqual(status["success"], 2)
		self.assertEqual(status["total_records"], 2)

	def test_mapped_select_still_shows_warning_but_unmapped_blocks_import(self):
		from frappe.core.doctype.data_import.value_mapping import (
			build_lookup_from_mappings,
			get_unmapped_invalid_values_for_column,
		)

		value_lookup = build_lookup_from_mappings(
			[
				{
					"reference_doctype": "Contact",
					"fieldname": "status",
					"parent_field": "",
					"source_value": "Pasiv",
					"target_value": "Passive",
				}
			]
		)
		col = Column(
			5,
			"Status",
			"Contact",
			["Opn", "Pasiv", "Open"],
			value_row_numbers=[2, 3, 4],
		)
		self.assertEqual(col.warnings[0]["type"], "value_mapping")
		self.assertIn("Opn", col.warnings[0]["message"])
		self.assertIn("Pasiv", col.warnings[0]["message"])
		self.assertIn("is not valid", col.warnings[0]["message"])
		self.assertIn("row 3 · Allowed:", col.warnings[0]["message"])
		unmapped = get_unmapped_invalid_values_for_column(col, value_lookup, "Contact")
		self.assertEqual(len(unmapped), 1)
		self.assertEqual(unmapped[0]["source"], "Opn")

	def test_sync_value_mappings_preserves_user_targets(self):
		from frappe.core.doctype.data_import.value_mapping import mapping_row_key, sync_value_mappings

		col = Column(
			5,
			"Status",
			"Contact",
			["Opn", "Pasiv", "Open"],
			value_row_numbers=[2, 3, 4],
		)
		import_file = frappe._dict(header=frappe._dict(columns=[col]))

		doc = frappe.get_doc(
			{
				"doctype": "Data Import",
				"reference_doctype": "Contact",
				"import_type": "Insert New Records",
				"value_mappings": [
					{
						"column": 6,
						"column_label": "Status",
						"fieldname": "status",
						"parent_field": "",
						"fieldtype": "Select",
						"select_options": "Open\nPassive",
						"source_value": "Pasiv",
						"target_value": "Passive",
						"row_numbers": "[3]",
						"no_of_rows": "1",
					}
				],
			}
		)
		# Child rows are Document objects after load — sync must accept them, not only dicts.
		self.assertTrue(hasattr(doc.value_mappings[0], "get"))

		self.assertTrue(sync_value_mappings(doc, import_file))
		rows = {mapping_row_key(row): row for row in doc.value_mappings}
		self.assertEqual(rows["6|status||Pasiv"].target_value, "Passive")
		self.assertIn("6|status||Opn", rows)
		self.assertEqual(rows["6|status||Opn"].target_value, "")

	def test_data_import_validate_populates_value_mappings(self):
		csv_content = "First Name,Status\nTest,Opn\n"
		import_file = frappe.get_doc(
			doctype="File",
			content=csv_content,
			file_name="data_import_invalid_status.csv",
			is_private=1,
		)
		import_file.save(ignore_permissions=True)

		data_import = frappe.get_doc(
			{
				"doctype": "Data Import",
				"reference_doctype": "Contact",
				"import_type": "Insert New Records",
				"import_file": import_file.file_url,
			}
		)
		data_import.insert()

		self.assertEqual(len(data_import.value_mappings), 1)
		self.assertEqual(data_import.value_mappings[0].fieldname, "status")
		self.assertEqual(data_import.value_mappings[0].source_value, "Opn")

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

	def test_no_of_rows_count_returns_row_count(self):
		from frappe.core.doctype.data_import.value_mapping import no_of_rows_count

		self.assertEqual(no_of_rows_count([]), "")
		self.assertEqual(no_of_rows_count([3]), "1")
		self.assertEqual(no_of_rows_count([2, 3, 4]), "3")

	def test_format_row_numbers_for_warning_truncates_long_lists(self):
		from frappe.core.doctype.data_import.importer import format_row_numbers_for_warning

		self.assertEqual(format_row_numbers_for_warning([2, 3, 4]), "2, 3, 4")
		self.assertEqual(
			format_row_numbers_for_warning([2, 3, 4, 5, 6, 7, 8, 9, 100]),
			"2, 3, 4, 5, 6, 7, ... 100",
		)

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

	def get_importer(self, doctype, import_file, update=False, use_sniffer=False, import_type=None):
		data_import = frappe.new_doc("Data Import")
		if import_type:
			data_import.import_type = import_type
		else:
			data_import.import_type = "Insert New Records" if not update else "Update Existing Records"
		data_import.reference_doctype = doctype
		data_import.import_file = import_file.file_url
		data_import.use_csv_sniffer = use_sniffer
		data_import.insert()
		frappe.db.commit()  # Commit so that the first import failure does not rollback the Data Import insert.  # nosemgrep
		_register_data_import_cleanup(self, data_import)

		return data_import

	def get_importer_semicolon(self, doctype, import_file, update=False, use_sniffer=False):
		data_import = frappe.new_doc("Data Import")
		data_import.import_type = "Insert New Records" if not update else "Update Existing Records"
		data_import.reference_doctype = doctype
		data_import.import_file = import_file.file_url
		data_import.use_csv_sniffer = use_sniffer
		# deliberately overwrite default delimiter options here, causing to fail when parsing `;`
		data_import.delimiter_options = ","
		data_import.insert()
		frappe.db.commit()  # nosemgrep
		_register_data_import_cleanup(self, data_import)

		return data_import


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
			doctype="File",
			content=frappe.read_file(full_path, raise_not_found=True),
			file_name=file_name,
			is_private=1,
		)
		f.save(ignore_permissions=True)

	return f


def get_csv_file_path(file_name):
	return frappe.get_app_path("frappe", "core", "doctype", "data_import", "fixtures", file_name)


class TestTreeDataImport(IntegrationTestCase):
	doctype_name = "Test Tree Data Import"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._ensure_tree_doctype()

	@classmethod
	def _ensure_tree_doctype(cls):
		if frappe.db.exists("DocType", cls.doctype_name):
			return

		from frappe.core.doctype.doctype.test_doctype import new_doctype

		dt = new_doctype(
			cls.doctype_name,
			is_tree=True,
			autoname="field:node_name",
			fields=[{"label": "Node Name", "fieldname": "node_name", "fieldtype": "Data", "reqd": 1}],
		)
		dt.allow_import = 1
		dt.insert()

	def _parent_label(self):
		meta = frappe.get_meta(self.doctype_name)
		parent_field = meta.nsm_parent_field
		return meta.get_field(parent_field).label

	def _make_csv_file(self, rows):
		parent_label = self._parent_label()
		lines = [f"Node Name,Is Group,{parent_label}"] + [",".join(row) for row in rows]
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"{frappe.generate_hash(length=10)}.csv",
				"content": "\n".join(lines),
				"is_private": 1,
			}
		)
		file_doc.save(ignore_permissions=True)  # test fixture — user context is not relevant here
		return file_doc

	def _get_importer(self, file_doc):
		data_import = frappe.new_doc("Data Import")
		data_import.import_type = "Insert New Records"
		data_import.reference_doctype = self.doctype_name
		data_import.import_file = file_doc.file_url
		data_import.insert()
		frappe.db.commit()  # Ensure Data Import insert is persisted before subsequent operations; # nosemgrep
		_register_data_import_cleanup(self, data_import)
		_register_file_cleanup(self, file_doc)
		return data_import

	def test_tree_preview_and_payload_order(self):
		rows = [
			("Leaf", "0", "Division"),
			("Division", "1", "Root"),
			("Root", "1", ""),
		]
		data_import = self._get_importer(self._make_csv_file(rows))
		preview = data_import.get_preview_from_template()

		self.assertIsNotNone(preview.tree_preview)
		self.assertEqual(preview.tree_preview.total_nodes, 3)
		node_ids = [node.id for node in preview.tree_preview.nodes]
		self.assertEqual(node_ids, ["Root", "Division", "Leaf"])

		imp = Importer(self.doctype_name, data_import=data_import)
		payload_ids = [p.doc.node_name for p in imp.import_file.get_payloads_for_import()]
		self.assertEqual(payload_ids, ["Root", "Division", "Leaf"])

	def test_tree_import(self):
		meta = frappe.get_meta(self.doctype_name)
		parent_field = meta.nsm_parent_field

		for name in ("Root", "Division", "Leaf"):
			frappe.delete_doc_if_exists(self.doctype_name, name)
		frappe.db.commit()  # ensure deletions are flushed to DB before import; # nosemgrep

		rows = [
			("Root", "1", ""),
			("Division", "1", "Root"),
			("Leaf", "0", "Division"),
		]
		data_import = self._get_importer(self._make_csv_file(rows))
		Importer(self.doctype_name, data_import=data_import).import_data()

		self.assertEqual(frappe.db.get_value(self.doctype_name, "Leaf", parent_field), "Division")

	def test_field_autoname_tree_skips_alias_mode(self):
		self.assertFalse(uses_tree_alias_references(self.doctype_name))
		self.assertIsNone(get_tree_alias_fieldname(self.doctype_name))

	def test_tree_preview_warns_non_group_parent(self):
		rows = [
			("Grandchild", "0", "Division"),
			("Division", "0", "Root"),
			("Root", "1", ""),
		]
		data_import = self._get_importer(self._make_csv_file(rows))
		preview = data_import.get_preview_from_template()

		division = next(node for node in preview.tree_preview.nodes if node.id == "Division")
		self.assertTrue(division.warnings)
		self.assertIn("Is Group is 0", division.warnings[0])


class TestTreeAliasDataImport(IntegrationTestCase):
	doctype_name = "Test Tree Alias Import"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._ensure_tree_doctype()

	@classmethod
	def _ensure_tree_doctype(cls):
		if frappe.db.exists("DocType", cls.doctype_name):
			return

		from frappe.core.doctype.doctype.test_doctype import new_doctype

		dt = new_doctype(
			cls.doctype_name,
			is_tree=True,
			autoname="TAL-.#####",
			title_field="node_label",
			fields=[{"label": "Node Label", "fieldname": "node_label", "fieldtype": "Data", "reqd": 1}],
		)
		dt.allow_import = 1
		dt.insert()

	def _parent_label(self):
		meta = frappe.get_meta(self.doctype_name)
		parent_field = meta.nsm_parent_field
		return meta.get_field(parent_field).label

	def _make_csv_file(self, rows, include_id=False):
		parent_label = self._parent_label()
		if include_id:
			header = f"ID,Node Label,Is Group,{parent_label}"
		else:
			header = f"Node Label,Is Group,{parent_label}"
		lines = [header] + [",".join(row) for row in rows]
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"{frappe.generate_hash(length=10)}.csv",
				"content": "\n".join(lines),
				"is_private": 1,
			}
		)
		file_doc.save(ignore_permissions=True)  # test fixture — user context is not relevant here
		return file_doc

	def _get_importer(self, file_doc, update=False, import_type=None):
		data_import = frappe.new_doc("Data Import")
		if import_type:
			data_import.import_type = import_type
		else:
			data_import.import_type = "Update Existing Records" if update else "Insert New Records"
		data_import.reference_doctype = self.doctype_name
		data_import.import_file = file_doc.file_url
		data_import.insert()
		frappe.db.commit()  # Ensure Data Import insert is persisted before subsequent operations; # nosemgrep
		_register_data_import_cleanup(self, data_import)
		_register_file_cleanup(self, file_doc)
		return data_import

	def _cleanup_docs(self, labels):
		for label in reversed(labels):
			name = frappe.db.get_value(self.doctype_name, {"node_label": label})
			if name:
				frappe.delete_doc(self.doctype_name, name, force=1)
		frappe.db.commit()  # Ensure deletions are flushed to DB before continuing; # nosemgrep

	def test_upsert_update_does_not_reset_omitted_defaults(self):
		"""UPSERT update must not overwrite fields omitted from the template with DocType defaults."""
		labels = ("Root Node",)
		self._cleanup_docs(labels)

		root = frappe.get_doc(
			{"doctype": self.doctype_name, "node_label": "Root Node", "is_group": 1}
		).insert()
		frappe.db.commit()  # nosemgrep

		rows = [(root.name, "Root Node Updated", "", "")]
		data_import = self._get_importer(self._make_csv_file(rows, include_id=True), import_type=UPSERT)
		Importer(self.doctype_name, data_import=data_import).import_data()

		self.assertEqual(frappe.db.get_value(self.doctype_name, root.name, "node_label"), "Root Node Updated")
		self.assertEqual(cint(frappe.db.get_value(self.doctype_name, root.name, "is_group")), 1)

		self._cleanup_docs(labels)

	def test_tree_alias_upsert_registers_updated_parent_for_children(self):
		"""UPSERT update path must register aliases so later rows resolve parent links."""
		meta = frappe.get_meta(self.doctype_name)
		parent_field = meta.nsm_parent_field
		labels = ("Root Node", "Child Node")
		self._cleanup_docs(labels)

		root = frappe.get_doc(
			{"doctype": self.doctype_name, "node_label": "Root Node", "is_group": 1}
		).insert()
		frappe.db.commit()  # nosemgrep

		rows = [
			(root.name, "Root Node", "1", ""),
			("", "Child Node", "0", "Root Node"),
		]
		data_import = self._get_importer(self._make_csv_file(rows, include_id=True), import_type=UPSERT)
		Importer(self.doctype_name, data_import=data_import).import_data()

		child_name = frappe.db.get_value(self.doctype_name, {"node_label": "Child Node"})
		self.assertTrue(child_name)
		self.assertEqual(frappe.db.get_value(self.doctype_name, child_name, parent_field), root.name)

		self._cleanup_docs(labels)

	def test_series_autoname_tree_uses_alias_mode(self):
		self.assertTrue(uses_tree_alias_references(self.doctype_name))
		self.assertEqual(get_tree_alias_fieldname(self.doctype_name), "node_label")

	def test_tree_alias_preview_and_payload_order(self):
		rows = [
			("Child Node", "0", "Root Node"),
			("Root Node", "1", ""),
		]
		data_import = self._get_importer(self._make_csv_file(rows))
		preview = data_import.get_preview_from_template()

		self.assertIsNotNone(preview.tree_preview)
		self.assertEqual(preview.tree_preview.total_nodes, 2)
		node_ids = [node.id for node in preview.tree_preview.nodes]
		self.assertEqual(node_ids, ["Root Node", "Child Node"])

		imp = Importer(self.doctype_name, data_import=data_import)
		header = imp.import_file.header
		payload_keys = [
			_get_tree_node_key(p.doc, header.id_fieldname, header.tree_alias_field)
			for p in imp.import_file.get_payloads_for_import()
		]
		self.assertEqual(payload_keys, ["Root Node", "Child Node"])

	def test_upsert_tree_preview_warns_missing_db_parent(self):
		rows = [("New Child", "0", "Missing Parent")]
		data_import = self._get_importer(self._make_csv_file(rows), import_type=UPSERT)
		preview = data_import.get_preview_from_template()

		child = next(node for node in preview.tree_preview.nodes if node.id == "New Child")
		self.assertTrue(
			any("Parent" in w and "not found in file" in w for w in child.warnings),
			"UPSERT should warn when an out-of-file parent is missing from the database",
		)

	def test_tree_alias_existing_db_parent_is_not_a_blocking_warning(self):
		"""Parent column aliases must resolve against DB title field, not document name."""
		from frappe.core.doctype.data_import.value_mapping import get_blocking_warnings

		existing_label = "Existing Root"
		self._cleanup_docs((existing_label, "New Child"))
		frappe.get_doc({"doctype": self.doctype_name, "node_label": existing_label, "is_group": 1}).insert()
		frappe.db.commit()  # nosemgrep

		rows = [("New Child", "0", existing_label)]
		data_import = self._get_importer(self._make_csv_file(rows))
		preview = data_import.get_preview_from_template()

		child = next(node for node in preview.tree_preview.nodes if node.id == "New Child")
		self.assertFalse(any("Parent" in w and "not found in file" in w for w in child.warnings))

		imp = Importer(self.doctype_name, data_import=data_import)
		self.assertEqual(
			get_blocking_warnings(imp.import_file.get_all_warnings(), imp.import_file, data_import), []
		)
		imp.import_data()
		self.assertTrue(frappe.db.get_value(self.doctype_name, {"node_label": "New Child"}))

		self._cleanup_docs((existing_label, "New Child"))

	def test_tree_preview_nests_subtree_with_external_db_parent(self):
		"""In-file subtree under a DB-only parent is nested in preview, not shown as orphans."""
		existing_label = "Existing Root"
		labels = (existing_label, "Branch A", "Branch B", "Branch C")
		self._cleanup_docs(labels)
		frappe.get_doc({"doctype": self.doctype_name, "node_label": existing_label, "is_group": 1}).insert()
		frappe.db.commit()  # nosemgrep

		rows = [
			("Branch C", "0", "Branch B"),
			("Branch B", "0", "Branch A"),
			("Branch A", "0", existing_label),
		]
		data_import = self._get_importer(self._make_csv_file(rows))
		preview = data_import.get_preview_from_template()

		nodes_by_id = {node.id: node for node in preview.tree_preview.nodes}
		for node_id in ("Branch A", "Branch B", "Branch C"):
			self.assertFalse(getattr(nodes_by_id[node_id], "orphan", False))
		self.assertEqual(nodes_by_id["Branch A"].depth, 0)
		self.assertEqual(nodes_by_id["Branch B"].depth, 1)
		self.assertEqual(nodes_by_id["Branch C"].depth, 2)

		self._cleanup_docs(labels)

	def test_tree_alias_import(self):
		meta = frappe.get_meta(self.doctype_name)
		parent_field = meta.nsm_parent_field
		labels = ("Root Node", "Child Node")
		self._cleanup_docs(labels)

		rows = [
			("Child Node", "0", "Root Node"),
			("Root Node", "1", ""),
		]
		data_import = self._get_importer(self._make_csv_file(rows))
		Importer(self.doctype_name, data_import=data_import).import_data()

		root_name = frappe.db.get_value(self.doctype_name, {"node_label": "Root Node"})
		child_name = frappe.db.get_value(self.doctype_name, {"node_label": "Child Node"})
		self.assertTrue(root_name)
		self.assertTrue(child_name)
		self.assertEqual(frappe.db.get_value(self.doctype_name, child_name, parent_field), root_name)

	def test_tree_alias_update_resolves_parent_link(self):
		"""UPDATE imports must resolve parent aliases to document names, like INSERT."""
		meta = frappe.get_meta(self.doctype_name)
		parent_field = meta.nsm_parent_field
		labels = ("Root Node", "Child Node")
		self._cleanup_docs(labels)

		root = frappe.get_doc(
			{"doctype": self.doctype_name, "node_label": "Root Node", "is_group": 1}
		).insert()
		child = frappe.get_doc(
			{
				"doctype": self.doctype_name,
				"node_label": "Child Node",
				"is_group": 0,
				parent_field: root.name,
			}
		).insert()
		frappe.db.commit()  # nosemgrep

		rows = [(child.name, "Child Node", "1", "Root Node")]
		data_import = self._get_importer(self._make_csv_file(rows, include_id=True), update=True)
		Importer(self.doctype_name, data_import=data_import).import_data()

		self.assertEqual(frappe.db.get_value(self.doctype_name, child.name, parent_field), root.name)
		self.assertEqual(cint(frappe.db.get_value(self.doctype_name, child.name, "is_group")), 1)

		self._cleanup_docs(labels)
