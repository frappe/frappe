import os
import unittest
from typing import List

import frappe
from frappe.core.doctype.data_import.data_import import export_json, import_doc
from frappe.desk.form.save import savedocs
from frappe.model.delete_doc import delete_doc


class TestFixtureImport(unittest.TestCase):
	def create_new_doctype(self, DocType: str) -> None:
		file = frappe.get_app_path("frappe", "custom", "fixtures", f"{DocType}.json")

		file = open(file, "r")
		doc = file.read()
		file.close()

		savedocs(doc, "Save")

	def insert_dummy_data_and_export(self, DocType: str, dummy_name_list: List[str]) -> str:
		for name in dummy_name_list:
			doc = frappe.get_doc({"doctype": DocType, "member_name": name})
			doc.insert()

		path_to_exported_fixtures = os.path.join(os.getcwd(), f"{DocType}_data.json")

		export_json(DocType, path_to_exported_fixtures)

		return path_to_exported_fixtures

	def test_fixtures_import(self):
		self.assertFalse(frappe.db.exists("DocType", "temp_doctype"))

		self.create_new_doctype("temp_doctype")

		dummy_name_list = ["jhon", "jane"]
		path_to_exported_fixtures = self.insert_dummy_data_and_export("temp_doctype", dummy_name_list)
		frappe.db.truncate("temp_doctype")

		import_doc(path_to_exported_fixtures)

		delete_doc("DocType", "temp_doctype", delete_permanently=True)
		os.remove(path_to_exported_fixtures)

		self.assertEqual(frappe.db.count("temp_doctype"), len(dummy_name_list))

		data = frappe.get_all("temp_doctype", "member_name")
		frappe.db.truncate("temp_doctype")

		imported_data = set()
		for item in data:
			imported_data.add(item["member_name"])

		self.assertEqual(set(dummy_name_list), imported_data)
