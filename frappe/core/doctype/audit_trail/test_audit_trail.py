# Copyright (c) 2023, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import today


class TestAuditTrail(IntegrationTestCase):
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

		comparator = create_comparator_doc("Test Custom Doctype for Doc Comparator", re_amended_doc.name)
		documents, results = comparator.compare_document()

		test_field_values = results["changed"]["Field"]
		self.check_expected_values(test_field_values, ["first value", "second value", "third value"])

	def test_compare_rows(self):
		doc = frappe.new_doc("Test Custom Doctype for Doc Comparator")
		doc.append("child_table_field", {"test_table_field": "old row 1 value"})
		doc.submit()
		doc.cancel()

		child_table_new = [{"test_table_field": "new row 1 value"}, {"test_table_field": "row 2 value"}]
		rows_updated = frappe._dict(child_table_field=child_table_new)
		amended_doc = amend_document(doc, {}, rows_updated, 1)

		comparator = create_comparator_doc("Test Custom Doctype for Doc Comparator", amended_doc.name)
		documents, results = comparator.compare_document()

		results = frappe._dict(results)
		self.check_rows_updated(results.row_changed)
		self.check_rows_added(results.added[amended_doc.name])

	def check_rows_updated(self, row_changed):
		self.assertIn("Child Table Field", row_changed)
		self.assertIn(0, row_changed["Child Table Field"])
		self.assertIn("Table Field", row_changed["Child Table Field"][0])
		table_field_values = row_changed["Child Table Field"][0]["Table Field"]
		self.check_expected_values(table_field_values, ["old row 1 value", "new row 1 value"])

	def check_rows_added(self, rows_added):
		self.assertIn("Child Table Field", rows_added)
		child_table = rows_added["Child Table Field"]
		self.assertIn("Table Field", child_table[0])
		self.check_expected_values(child_table[0]["Table Field"], "row 2 value")

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
					"in_list_view": 1,
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
		amended_doc.set(child_table, rows_updated[child_table])
	if submit:
		amended_doc.submit()
	return amended_doc


def create_comparator_doc(doctype_name, document):
	comparator = frappe.new_doc("Audit Trail")
	args_dict = {
		"doctype_name": doctype_name,
		"document": document,
		"start_date": today(),
		"end_date": today(),
	}
	comparator.update(args_dict)
	return comparator
