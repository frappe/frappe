# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.custom.doctype.custom_field.custom_field import (
	create_custom_field,
	create_custom_fields,
	rename_fieldname,
)
from frappe.tests import IntegrationTestCase


class TestCustomField(IntegrationTestCase):
	def test_create_custom_fields(self):
		create_custom_fields(
			{
				"Address": [
					{
						"fieldname": "_test_custom_field_1",
						"label": "_Test Custom Field 1",
						"fieldtype": "Data",
						"insert_after": "phone",
					},
				],
				("Address", "Contact"): [
					{
						"fieldname": "_test_custom_field_2",
						"label": "_Test Custom Field 2",
						"fieldtype": "Data",
						"insert_after": "phone",
					},
				],
			}
		)

		frappe.db.commit()

		self.assertTrue(frappe.db.exists("Custom Field", "Address-_test_custom_field_1"))
		self.assertTrue(frappe.db.exists("Custom Field", "Address-_test_custom_field_2"))
		self.assertTrue(frappe.db.exists("Custom Field", "Contact-_test_custom_field_2"))

	def test_custom_field_sorting(self):
		try:
			custom_fields = {
				"ToDo": [
					{"fieldname": "a_test_field", "insert_after": "b_test_field"},
					{"fieldname": "b_test_field", "insert_after": "status"},
					{"fieldname": "c_test_field", "insert_after": "unknown_custom_field"},
					{"fieldname": "d_test_field", "insert_after": "status"},
				]
			}

			create_custom_fields(custom_fields, ignore_validate=True)

			fields = frappe.get_meta("ToDo", cached=False).fields

			for i, field in enumerate(fields):
				if field.fieldname == "b_test_field":
					self.assertEqual(fields[i - 1].fieldname, "status")

				if field.fieldname == "d_test_field":
					self.assertEqual(fields[i - 1].fieldname, "a_test_field")

			self.assertEqual(fields[-1].fieldname, "c_test_field")

		finally:
			frappe.db.delete(
				"Custom Field",
				{
					"dt": "ToDo",
					"fieldname": (
						"in",
						(
							"a_test_field",
							"b_test_field",
							"c_test_field",
							"d_test_field",
						),
					),
				},
			)

			# undo changes commited by DDL
			# nosemgrep
			frappe.db.commit()

	def test_custom_section_and_column_breaks_ordering(self):
		doc = frappe.get_doc(
			{
				"doctype": "DocType",
				"name": "Test Custom Breaks Ordering",
				"custom": 1,
				"module": "Core",
				"fields": [
					{"fieldname": "section1", "fieldtype": "Section Break", "label": "Section 1"},
					{"fieldname": "field1", "fieldtype": "Data", "label": "Field 1"},
					{"fieldname": "field2", "fieldtype": "Data", "label": "Field 2"},
					{"fieldname": "section2", "fieldtype": "Section Break", "label": "Section 2"},
					{"fieldname": "column21", "fieldtype": "Column Break", "label": "Column 2.1"},
					{"fieldname": "field3", "fieldtype": "Data", "label": "Field 3"},
					{"fieldname": "column22", "fieldtype": "Column Break", "label": "Column 2.2"},
					{"fieldname": "field4", "fieldtype": "Data", "label": "Field 4"},
				],
			}
		)
		doc.insert()

		# Add a custom Section Break after the first section
		custom_section = frappe.get_doc(
			{
				"doctype": "Custom Field",
				"dt": "Test Custom Breaks Ordering",
				"fieldname": "custom_section",
				"fieldtype": "Section Break",
				"insert_after": "section1",
				"label": "Custom Section",
			}
		)
		custom_section.insert()

		# Append a custom Column Break to the second section
		custom_column = frappe.get_doc(
			{
				"doctype": "Custom Field",
				"dt": "Test Custom Breaks Ordering",
				"fieldname": "custom_column_insert",
				"fieldtype": "Column Break",
				"insert_after": "column21",
				"label": "Custom Column Insert",
			}
		)
		custom_column.insert()

		# Add a custom Column Break within the second section
		custom_column = frappe.get_doc(
			{
				"doctype": "Custom Field",
				"dt": "Test Custom Breaks Ordering",
				"fieldname": "custom_column_end",
				"fieldtype": "Column Break",
				"insert_after": "section2",
				"label": "Custom Column End",
			}
		)
		custom_column.insert()

		# Get the updated DocType metadata to get the updated field order
		updated_meta = frappe.get_meta("Test Custom Breaks Ordering", cached=False)
		field_names = [field.fieldname for field in updated_meta.fields]

		# Assert the correct ordering of fields
		expected_order = [
			"section1",
			"field1",
			"field2",
			"custom_section",
			"section2",
			"column21",
			"field3",
			"custom_column_insert",
			"column22",
			"field4",
			"custom_column_end",
		]
		self.assertEqual(field_names, expected_order)

	def test_custom_field_renaming(self):
		def gen_fieldname():
			return "test_" + frappe.generate_hash()

		field = create_custom_field("ToDo", {"label": gen_fieldname()}, is_system_generated=False)
		old = field.fieldname
		new = gen_fieldname()
		data = frappe.generate_hash()
		doc = frappe.get_doc({"doctype": "ToDo", old: data, "description": "Something"}).insert()

		rename_fieldname(field.name, new)
		field.reload()
		self.assertEqual(field.fieldname, new)

		doc = frappe.get_doc("ToDo", doc.name)  # doc.reload doesn't clear old fields.
		self.assertEqual(doc.get(new), data)
		self.assertFalse(doc.get(old))

		field.delete()
