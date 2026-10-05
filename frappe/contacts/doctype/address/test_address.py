# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
from functools import partial

import frappe
<<<<<<< HEAD
from frappe.contacts.doctype.address.address import address_query, get_address_display
from frappe.tests.utils import FrappeTestCase
=======
from frappe.contacts.doctype.address.address import (
	address_query,
	get_address_display,
	get_address_list,
	get_list_context,
)
from frappe.permissions import add_permission, update_permission_property
from frappe.tests import IntegrationTestCase
>>>>>>> f3ba360 (fix(address): let select-only users search linked addresses)


class TestAddress(FrappeTestCase):
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
		self.assertEqual(len(query(filters={"link_doctype": "User", "link_name": "_Test No Address"})), 0)

	def test_address_query_with_only_select_permission(self):
		address = frappe.get_doc(
			{
				"address_title": "_Test Select Only Address",
				"address_line1": "1",
				"city": "Mumbai",
				"country": "India",
				"doctype": "Address",
				"links": [{"link_doctype": "User", "link_name": "Administrator"}],
			}
		).insert()

		role = frappe.new_doc("Role", role_name=frappe.generate_hash()).insert().name
		add_permission("Address", role, 0, ptype="select")
		update_permission_property("Address", role, 0, "read", 0, validate=False)
		# "All" grants owner-only read, which would lift the user above select
		update_permission_property("Address", "All", 0, "read", 0, validate=False)
		user = frappe.get_doc(
			doctype="User",
			email=f"select-{frappe.generate_hash(length=8)}@example.com",
			first_name="Select Only",
			send_welcome_email=0,
			roles=[{"role": role}],
		).insert()

		filters = {"link_doctype": "User", "link_name": "Administrator"}
		with self.set_user(user.name):
			results = address_query("Address", address.name, "name", 0, 10, filters)
		self.assertEqual(results[0][0], address.name)
