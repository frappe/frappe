# Copyright (c) 2023, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestDocumentComparator(FrappeTestCase):
	def setUp(self):
		self.child_doctype = create_custom_child_doctype()
		self.custom_doctype = create_custom_doctype()

	def test_compare_changed_fields(self):
		doc = frappe.new_doc("Test Custom Doctype for Doc Comparator")
		doc.test_field = "first value"
		doc.submit()
		doc.cancel()

		changed_fields = frappe._dict(test_field="second value")
		amended_doc = amend_document(doc, changed_fields, {}, 1)
		amended_doc.cancel()

		changed_fields = frappe._dict(test_field="third value")
		re_amended_doc = amend_document(amended_doc, changed_fields, {}, 1)

		comparator = create_comparator_doc("Test Custom Doctype for Doc Comparator", doc.name)
		documents, results = comparator.compare_document()

		test_field_values = results["changed"]["Field"]
		self.check_expected_values(test_field_values, ["first value", "second value", "third value"])

	def test_compare_rows_updated(self):
		doc = frappe.new_doc("Test Custom Doctype for Doc Comparator")
		doc.append("child_table_field", {"test_table_field": "old row value"})
		doc.submit()
		doc.cancel()

		rows_updated = frappe._dict(child_table_field={"test_table_field": "new row value"})
		amended_doc = amend_document(doc, {}, rows_updated, 1)

		comparator = create_comparator_doc("Test Custom Doctype for Doc Comparator", doc.name)
		documents, results = comparator.compare_document()

		table_field_values = results["row_changed"]["Child Table Field"][0]["Table Field"]
		self.check_expected_values(table_field_values, ["old row value", "new row value"])

	def check_expected_values(self, values_to_check, expected_values):
		for i in range(len(values_to_check)):
			self.assertEqual(values_to_check[i], expected_values[i])

	def tearDown(self):
		self.child_doctype.delete()
		self.custom_doctype.delete()


def create_custom_child_doctype():
	child_doctype = frappe.get_doc(
		{
			"doctype": "DocType",
			"module": "Core",
			"name": "Test Custom Child for Doc Comparator",
			"custom": 1,
			"istable": 1,
			"fields": [
				{
					"label": "Table Field",
					"fieldname": "test_table_field",
					"fieldtype": "Data",
				},
			],
		}
	).insert(ignore_if_duplicate=True)
	return child_doctype


def create_custom_doctype():
	custom_doctype = frappe.get_doc(
		{
			"doctype": "DocType",
			"module": "Core",
			"name": "Test Custom Doctype for Doc Comparator",
			"custom": 1,
			"is_submittable": 1,
			"fields": [
				{
					"label": "Field",
					"fieldname": "test_field",
					"fieldtype": "Data",
				},
				{
					"label": "Child Table Field",
					"fieldname": "child_table_field",
					"fieldtype": "Table",
					"options": "Test Custom Child for Doc Comparator",
				},
			],
			"permissions": [{"role": "System Manager", "read": 1}],
		}
	).insert(ignore_if_duplicate=True)
	return custom_doctype


def amend_document(amend_from, changed_fields, rows_updated, submit=False):
	amended_doc = frappe.copy_doc(amend_from)
	amended_doc.amended_from = amend_from.name
	amended_doc.update(changed_fields)
	for child_table in rows_updated:
		amended_doc.set(child_table, [])
		amended_doc.append(child_table, rows_updated[child_table])
	if submit:
		amended_doc.submit()
	return amended_doc


def create_comparator_doc(doctype_name, document):
	comparator = frappe.new_doc("Document Comparator")
	comparator.doctype_name = doctype_name
	comparator.document = document
	return comparator
