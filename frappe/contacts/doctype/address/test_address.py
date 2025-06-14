# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
from functools import partial

import frappe
from frappe.contacts.doctype.address.address import address_query, get_address_display
from frappe.tests import IntegrationTestCase


class TestAddress(IntegrationTestCase):
	def test_template_works(self):
		if not frappe.db.exists("Address Template", "India"):
			frappe.get_doc({"doctype": "Address Template", "country": "India", "is_default": 1}).insert()

		if not frappe.db.exists("Address", "_Test Address-Office"):
			frappe.get_doc(
				{
					"address_line1": "_Test Address Line 1",
					"address_title": "_Test Address",
					"address_type": "Office",
					"city": "_Test City",
					"state": "Test State",
					"country": "India",
					"doctype": "Address",
					"is_primary_address": 1,
					"phone": "+91 0000000000",
				}
			).insert()

		address = frappe.get_list("Address")[0].name
		display = get_address_display(frappe.get_doc("Address", address).as_dict())
		self.assertTrue(display)

	def test_address_query(self):
		def query(doctype="Address", txt="", searchfield="name", start=0, page_len=20, filters=None):
			if filters is None:
				filters = {"link_doctype": "User", "link_name": "Administrator"}
			return address_query(doctype, txt, searchfield, start, page_len, filters)

		frappe.get_doc(
			{
				"address_type": "Billing",
				"address_line1": "1",
				"city": "Mumbai",
				"state": "Maharashtra",
				"country": "India",
				"doctype": "Address",
				"links": [
					{
						"link_doctype": "User",
						"link_name": "Administrator",
					}
				],
			}
		).insert()

		self.assertGreaterEqual(len(query(txt="Admin")), 1)
		self.assertEqual(len(query(txt="what_zyx")), 0)
