# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

# test_records = frappe.get_test_records('DocType')

class TestDocType(unittest.TestCase):
	def new_doctype(self, name):
		return frappe.get_doc({
			"doctype": "DocType",
			"module": "Core",
			"custom": 1,
			"fields": [{"label": "Some Field", "fieldname": "some_fieldname", "fieldtype": "Data"}],
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