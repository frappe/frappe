# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe, unittest
test_records = frappe.get_test_records('Address')

from frappe.geo.doctype.address.address import get_address_display

class TestAddress(unittest.TestCase):
	def test_template_works(self):
		address = frappe.get_list("Address")[0].name
		display = get_address_display(frappe.get_doc("Address", address).as_dict())
		self.assertTrue(display)


test_dependencies = ["Address Template"]
