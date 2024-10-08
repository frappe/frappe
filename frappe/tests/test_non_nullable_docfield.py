import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.database.schema import DBTable
from frappe.tests import IntegrationTestCase


class TestNonNullableDocfield(IntegrationTestCase):
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
		query = "SELECT column_name AS name, column_default is NULL AS default_null,is_nullable = 'NO' AS not_nullable FROM information_schema.columns WHERE table_name=%s"
		for column in frappe.db.sql(query, table.table_name, as_dict=True):
			if column.name == "test_field":
				self.assertFalse(column.not_nullable)

		doctype_doc = frappe.get_doc("DocType", self.nullable_doctype_name)
		for field in doctype_doc.fields:
			if field.fieldname == "test_field":
				field.not_nullable = 1
				break
		doctype_doc.save()
		for column in frappe.db.sql(query, table.table_name, as_dict=True):
			if column.name == "test_field":
				self.assertFalse(column.default_null)
				self.assertTrue(column.not_nullable)
		inserted_doc = frappe.db.get(self.nullable_doctype_name, {"name": doc.name})
		self.assertEqual(inserted_doc.test_field, "")
