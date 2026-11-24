# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
from functools import partial
from unittest.mock import patch

import frappe
from frappe.contacts.doctype.address.address import (
	address_query,
	get_address_display,
	get_address_list,
	get_list_context,
)
from frappe.core.doctype.user.test_user import test_user
from frappe.permissions import add_permission, update_permission_property
from frappe.tests import IntegrationTestCase


class TestAddress(IntegrationTestCase):
	def create_test_address(self, address_title="_Test Address", address_type="Office"):
		if not frappe.db.exists("Address Template", "India"):
			frappe.get_doc({"doctype": "Address Template", "country": "India", "is_default": 1}).insert()

		address = frappe.db.get_value(
			"Address", {"address_title": address_title, "address_type": address_type}
		)
		if not address:
			address = (
				frappe.get_doc(
					{
						"address_line1": "_Test Address Line 1",
						"address_title": address_title,
						"address_type": address_type,
						"city": "_Test City",
						"state": "Test State",
						"country": "India",
						"doctype": "Address",
						"is_primary_address": 1,
						"phone": "+91 0000000000",
					}
				)
				.insert()
				.name
			)

		return address

	def test_template_works(self):
		self.create_test_address()

		address = frappe.get_list("Address")[0].name
		display = get_address_display(frappe.get_doc("Address", address).as_dict())
		self.assertTrue(display)

	def test_get_address_list_sets_display(self):
		address = self.create_test_address()

		rows = get_address_list("Address", None, [["name", "=", address]], 0)

		self.assertEqual(rows[0].name, address)
		self.assertEqual(rows[0].address_display, get_address_display(rows[0]))

	def test_get_address_list_accepts_dict_filters(self):
		address = self.create_test_address()

		rows = get_address_list("Address", None, frappe._dict(name=address), 0)

		self.assertEqual(rows[0].name, address)
		self.assertEqual(rows[0].address_display, get_address_display(rows[0]))

	def test_get_address_list_reuses_address_templates(self):
		addresses = {
			self.create_test_address(),
			self.create_test_address(address_title="_Test Address Two"),
		}

		with patch.object(frappe.db, "get_value", wraps=frappe.db.get_value) as get_value:
			rows = get_address_list("Address", None, [["name", "in", list(addresses)]], 0)

		self.assertEqual({row.name for row in rows}, addresses)
		address_template_calls = [
			call for call in get_value.call_args_list if call.args and call.args[0] == "Address Template"
		]
		self.assertEqual(address_template_calls, [])

	def test_get_list_context_preserves_page_template(self):
		context = get_list_context(frappe._dict(template="www/portal.html"))

		self.assertEqual(context.template, "www/portal.html")
		self.assertEqual(context.list_template, "templates/includes/list/list.html")

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

	def test_portal_user_reads_addresses_linked_to_their_contacts_with_their_email(self):
		with test_user(roles=[], generated_id=True) as user:
			contact = frappe.get_doc("Contact", {"user": user.name})
			contact.append("links", {"link_doctype": "User", "link_name": "Administrator"})
			contact.save()
			second_contact = frappe.get_doc(
				doctype="Contact",
				first_name="_Test Second Contact",
				user=user.name,
				links=[{"link_doctype": "User", "link_name": "Guest"}],
			)
			second_contact.add_email(user.email, is_primary=True)
			second_contact.insert()
			frappe.get_doc(
				doctype="Contact",
				first_name="_Test Stale Contact",
				user=user.name,
				email_ids=[{"email_id": "_test_stale@example.com", "is_primary": 1}],
				links=[{"link_doctype": "User", "link_name": "test1@example.com"}],
			).insert()

			first, second, stale, other = (
				frappe.get_doc(
					doctype="Address",
					address_line1="1",
					city="Mumbai",
					country="India",
					links=[{"link_doctype": "User", "link_name": link_name}],
				).insert()
				for link_name in ("Administrator", "Guest", "test1@example.com", "test@example.com")
			)

			with self.set_user(user.name):
				self.assertTrue(frappe.has_website_permission(first))
				self.assertTrue(frappe.has_website_permission(second))
				self.assertFalse(frappe.has_website_permission(stale))
				self.assertFalse(frappe.has_website_permission(other))

	def test_guest_gets_nothing_from_a_contact_linked_to_guest(self):
		frappe.get_doc(
			doctype="Contact",
			first_name="_Test Guest Contact",
			user="Guest",
			email_ids=[{"email_id": frappe.db.get_value("User", "Guest", "email"), "is_primary": 1}],
			links=[{"link_doctype": "User", "link_name": "test1@example.com"}],
		).insert()
		address = frappe.get_doc(
			doctype="Address",
			address_line1="1",
			city="Mumbai",
			country="India",
			links=[{"link_doctype": "User", "link_name": "test1@example.com"}],
		).insert()

		with self.set_user("Guest"):
			self.assertFalse(frappe.has_website_permission(address))
