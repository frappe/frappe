# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

# test_records = frappe.get_test_records('DocType')


class TestDocType(unittest.TestCase):
	def new_doctype(self, name, unique=0):
		return frappe.get_doc({
			"doctype": "DocType",
			"module": "Core",
			"custom": 1,
			"fields": [{"label": "Some Field", "fieldname": "some_fieldname", "fieldtype": "Data", "unique": unique}],
			"permissions": [{"role": "System Manager", "read": 1}],
			"name": name
		})

	def test_validate_name(self):
		self.assertRaises(frappe.NameError, self.new_doctype("_Some DocType").insert)
		self.assertRaises(frappe.NameError, self.new_doctype("8Some DocType").insert)
		self.assertRaises(frappe.NameError, self.new_doctype("Some (DocType)").insert)
		for name in ("Some DocType", "Some_DocType"):
			if frappe.db.exists("DocType", name):
				frappe.delete_doc("DocType", name)

			doc = self.new_doctype(name).insert()
			doc.delete()

	def test_doctype_unique_constraint_dropped(self):
		if frappe.db.exists("DocType", "With_Unique"):
			frappe.delete_doc("DocType", "With_Unique")

		dt = self.new_doctype("With_Unique", unique=1)
		dt.insert()

		doc1 = frappe.new_doc("With_Unique")
		doc2 = frappe.new_doc("With_Unique")
		doc1.some_fieldname = "Something"
		doc1.name = "one"
		doc2.some_fieldname = "Something"
		doc2.name = "two"

		doc1.insert()
		self.assertRaises(frappe.UniqueValidationError, doc2.insert)

		dt.fields[0].unique = 0
		dt.save()

		doc2.insert()
		doc1.delete()
		doc2.delete()
