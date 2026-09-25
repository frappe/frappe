# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.custom.doctype.custom_field.custom_field import (
	create_custom_field,
	create_custom_fields,
	delete_custom_fields,
	rename_fieldname,
)
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
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

	def test_delete_custom_fields(self):
		doctype = "ToDo"
		fields = [
			{
				"fieldname": f"test_delete_{frappe.generate_hash(length=5)}",
				"fieldtype": "Data",
				"insert_after": "status",
			}
			for _ in range(4)
		]
		fieldnames = [f["fieldname"] for f in fields]

		create_custom_fields({doctype: fields})

		# create property setters for fields deleted via safe path (hooks should clean these up)
		for fieldname in fieldnames[:2]:
			make_property_setter(doctype, fieldname, "hidden", "1", "Check")

		def field_exists(fieldname):
			return frappe.db.exists("Custom Field", {"fieldname": fieldname, "dt": doctype})

		def property_setter_exists(fieldname):
			return frappe.db.exists("Property Setter", {"doc_type": doctype, "field_name": fieldname})

		for fieldname in fieldnames:
			self.assertTrue(field_exists(fieldname))
		for fieldname in fieldnames[:2]:
			self.assertTrue(property_setter_exists(fieldname))

		# 1
		delete_custom_fields({doctype: [fieldnames[0], fieldnames[0]]})
		self.assertFalse(field_exists(fieldnames[0]))
		self.assertFalse(property_setter_exists(fieldnames[0]))

		# 2
		delete_custom_fields({doctype: [{"fieldname": fieldnames[1]}]})
		self.assertFalse(field_exists(fieldnames[1]))
		self.assertFalse(property_setter_exists(fieldnames[1]))

		# 3
		delete_custom_fields({doctype: [fieldnames[2], fieldnames[2]]}, bypass_hooks=True)
		self.assertFalse(field_exists(fieldnames[2]))

		# 4
		delete_custom_fields({doctype: [{"fieldname": fieldnames[3]}]}, bypass_hooks=True)
		self.assertFalse(field_exists(fieldnames[3]))
