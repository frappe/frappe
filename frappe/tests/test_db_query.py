# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe, unittest

from frappe.model.db_query import DatabaseQuery

class TestReportview(unittest.TestCase):
	def test_basic(self):
		self.assertTrue({"name":"DocType"} in DatabaseQuery("DocType").execute(limit_page_length=None))

	def test_fields(self):
		self.assertTrue({"name":"DocType", "issingle":0} \
			in DatabaseQuery("DocType").execute(fields=["name", "issingle"], limit_page_length=None))

	def test_filters_1(self):
		self.assertFalse({"name":"DocType"} \
			in DatabaseQuery("DocType").execute(filters=[["DocType", "name", "like", "J%"]]))

	def test_filters_2(self):
		self.assertFalse({"name":"DocType"} \
			in DatabaseQuery("DocType").execute(filters=[{"name": ["like", "J%"]}]))

	def test_filters_3(self):
		self.assertFalse({"name":"DocType"} \
			in DatabaseQuery("DocType").execute(filters={"name": ["like", "J%"]}))

	def test_filters_4(self):
		self.assertTrue({"name":"DocField"} \
			in DatabaseQuery("DocType").execute(filters={"name": "DocField"}))

	def test_or_filters(self):
		data = DatabaseQuery("DocField").execute(
				filters={"parent": "DocType"}, fields=["fieldname", "fieldtype"],
				or_filters=[{"fieldtype":"Table"}, {"fieldtype":"Select"}])

		self.assertTrue({"fieldtype":"Table", "fieldname":"fields"} in data)
		self.assertTrue({"fieldtype":"Select", "fieldname":"document_type"} in data)
		self.assertFalse({"fieldtype":"Check", "fieldname":"issingle"} in data)
