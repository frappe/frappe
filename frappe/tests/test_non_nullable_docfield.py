import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.database.schema import DBTable
from frappe.tests.utils import FrappeTestCase


class TestNonNullableDocfield(FrappeTestCase):
	def setUp(self):
		doc = new_doctype(
			fields=[
				{
					"fieldname": "test_field",
					"fieldtype": "Data",
					"label": "test_field",
					"not_nullable": 1,
				},
			],
		)
		doc.insert()
		self.doctype_name = doc.name

		nullable_doc = new_doctype(
			fields=[
				{
					"fieldname": "test_field",
					"fieldtype": "Data",
					"label": "test_field",
				}
			]
		)
		nullable_doc.insert()
		self.nullable_doctype_name = nullable_doc.name

	def test_non_nullable_field(self):
		doc = frappe.new_doc(doctype=self.doctype_name)
		doc.insert()
		inserted_doc = frappe.db.get(self.doctype_name, {"name": doc.name})
		self.assertEqual(inserted_doc.test_field, "")

	def test_edit_field_nullable_status(self):
		doc = frappe.new_doc(doctype=self.nullable_doctype_name)
		doc.insert()
		inserted_doc = frappe.db.get(self.nullable_doctype_name, {"name": doc.name})
		self.assertEqual(inserted_doc.test_field, None)
		table = DBTable(self.nullable_doctype_name)
		column_data = frappe.db.get_table_columns_description(table.table_name)
		for column in column_data:
			if column.name == "test_field":
				self.assertEqual(column.default, "NULL")
				self.assertFalse(column.not_nullable)

		doctype_doc = frappe.get_doc("DocType", self.nullable_doctype_name)
		doctype_doc.fields[0].not_nullable = 1
		doctype_doc.save()
		column_data = frappe.db.get_table_columns_description(table.table_name)
		for column in column_data:
			if column.name == "test_field":
				self.assertEqual(column.default, "''")
				self.assertIsNotNone(column.default)
				self.assertTrue(column.not_nullable)
		inserted_doc = frappe.db.get(self.nullable_doctype_name, {"name": doc.name})
		self.assertEqual(inserted_doc.test_field, "")
