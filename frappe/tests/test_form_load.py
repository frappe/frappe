# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe, unittest
from frappe.widgets.form.meta import get_meta
from frappe.widgets.form.load import getdoctype, getdoc 

class TestFormLoad(unittest.TestCase):
	def test_load(self):
		getdoctype("DocType")
		self.assertEquals(frappe.response.docs[0].name, "DocType")
		self.assertTrue(frappe.response.docs[0].get("__js"))

		frappe.response.docs = []
		d = getdoctype("Event")
		self.assertTrue(frappe.response.docs[0].get("__calendar_js"))
