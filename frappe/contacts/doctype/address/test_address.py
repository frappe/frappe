# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe, unittest
from frappe.contacts.doctype.address.address import get_address_display

class TestAddress(unittest.TestCase):
	def test_template_works(self):
		if not frappe.db.exists('Address Template', 'India'):
			frappe.get_doc({
				"doctype": "Address Template",
				"country": 'India',
				"is_default": 1
			}).insert()

		if not frappe.db.exists('Address', '_Test Address-Office'):
			frappe.get_doc({
				"address_line1": "_Test Address Line 1",
				"address_title": "_Test Address",
				"address_type": "Office",
				"city": "_Test City",
				"state": "Test State",
				"country": "India",
				"doctype": "Address",
				"is_primary_address": 1,
				"phone": "+91 0000000000"
			}).insert()

		address = frappe.get_list("Address")[0].name
		display = get_address_display(frappe.get_doc("Address", address).as_dict())
		self.assertTrue(display)