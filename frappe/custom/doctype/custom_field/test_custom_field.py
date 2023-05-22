# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.tests.utils import FrappeTestCase

test_records = frappe.get_test_records("Custom Field")


class TestCustomField(FrappeTestCase):
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
