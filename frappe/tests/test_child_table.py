from typing import Callable

import frappe
from frappe.model import child_table_fields
from frappe.tests.utils import FrappeTestCase


class TestChildTable(FrappeTestCase):
	def tearDown(self) -> None:
		try:
			frappe.delete_doc("DocType", self.doctype_name, force=1)
		except Exception:
			pass

	def test_child_table_doctype_creation_and_transitioning(self) -> None:
		"""
		This method tests the creation of child table doctype
		as well as it's transitioning from child table to normal and normal to child table doctype
		"""

		self.doctype_name = "Test Newy Child Table"

		try:
			doc = frappe.get_doc(
				{
					"doctype": "DocType",
					"name": self.doctype_name,
					"istable": 1,
					"custom": 1,
					"module": "Integrations",
					"fields": [
						{"label": "Some Field", "fieldname": "some_fieldname", "fieldtype": "Data", "reqd": 1}
					],
				}
			).insert(ignore_permissions=True)
		except Exception:
			self.fail("Not able to create Child Table Doctype")

		for column in child_table_fields:
			self.assertTrue(frappe.db.has_column(self.doctype_name, column))

		# check transitioning from child table to normal doctype
		doc.istable = 0
		try:
			doc.save(ignore_permissions=True)
		except Exception:
			self.fail("Not able to transition from Child Table Doctype to Normal Doctype")

		self.check_valid_columns(self.assertFalse)

		# check transitioning from normal to child table doctype
		doc.istable = 1
		try:
			doc.save(ignore_permissions=True)
		except Exception:
			self.fail("Not able to transition from Normal Doctype to Child Table Doctype")

		self.check_valid_columns(self.assertTrue)

	def check_valid_columns(self, assertion_method: Callable) -> None:
		valid_columns = frappe.get_meta(self.doctype_name).get_valid_columns()
		for column in child_table_fields:
			assertion_method(column in valid_columns)
