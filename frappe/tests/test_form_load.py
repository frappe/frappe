# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe, unittest
from frappe.desk.form.meta import get_meta
from frappe.desk.form.load import getdoctype, getdoc 

class TestFormLoad(unittest.TestCase):
	def test_load(self):
		getdoctype("DocType")
		meta = filter(lambda d: d.name=="DocType", frappe.response.docs)[0]
		self.assertEquals(meta.name, "DocType")
		self.assertTrue(meta.get("__js"))

		frappe.response.docs = []
		d = getdoctype("Event")
		meta = filter(lambda d: d.name=="Event", frappe.response.docs)[0]
		self.assertTrue(meta.get("__calendar_js"))
