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

	def test_domainification(self):
		domain = frappe.new_doc({
			"doctype": "Domain",
			"domain": "_Test Domain"
		}).insert()

		# add domain in active domains
		domain_settings = frappe.get_doc("Domain Settings", "Domain Settings")
		row = domain_settings.append("active_domains", {})
		row.domain = domain.name
		domain_settings.save()

		doc = self.new_doctype("_Test Domainification")
		doc.restrict_to_domain = domain.name
		doc.insert()