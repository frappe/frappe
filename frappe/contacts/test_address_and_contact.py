# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
import frappe.contacts.address_and_contact as address_and_contact_module
from frappe.contacts.address_and_contact import get_permission_query_conditions, has_permission, remove_link
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_user_permission, remove_user_permission
from frappe.tests import IntegrationTestCase

PRIMARY_FIELDS = {
	"ToDo": [
		{
			"fieldname": "primary_address",
			"label": "Primary Address",
			"fieldtype": "Link",
			"options": "Address",
		},
		{
			"fieldname": "primary_city",
			"label": "Primary City",
			"fieldtype": "Data",
			"fetch_from": "primary_address.city",
		},
	]
}


class TestRemoveLink(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_custom_fields(PRIMARY_FIELDS)
		cls.addClassCleanup(cls.drop_primary_fields)

	@staticmethod
	def drop_primary_fields():
		for field in PRIMARY_FIELDS["ToDo"]:
			frappe.delete_doc("Custom Field", f"ToDo-{field['fieldname']}", force=True)
		frappe.clear_cache(doctype="ToDo")

	def setUp(self):
		self.document = frappe.get_doc({"doctype": "ToDo", "description": "_Test Remove Link"}).insert()
		self.other_document = frappe.get_doc(
			{"doctype": "ToDo", "description": "_Test Remove Link Other"}
		).insert()

	def create_address(self, links):
		return frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "_Test Delink Address",
				"address_type": "Billing",
				"address_line1": "_Test Address Line 1",
				"city": "_Test City",
				"country": "India",
				"links": links,
			}
		).insert()

	def link_to(self, doc):
		return {"link_doctype": doc.doctype, "link_name": doc.name}

	def test_removes_only_the_given_document(self):
		address = self.create_address([self.link_to(self.document), self.link_to(self.other_document)])

		remove_link("Address", address.name, self.document.doctype, self.document.name)

		address.reload()
		self.assertEqual(
			[(link.link_doctype, link.link_name) for link in address.links],
			[(self.other_document.doctype, self.other_document.name)],
		)

	def test_keeps_the_address_itself(self):
		address = self.create_address([self.link_to(self.document)])

		remove_link("Address", address.name, self.document.doctype, self.document.name)

		self.assertTrue(frappe.db.exists("Address", address.name))
		self.assertEqual(frappe.get_doc("Address", address.name).links, [])

	def test_unknown_document_is_a_no_op(self):
		address = self.create_address([self.link_to(self.document)])
		modified_before = frappe.db.get_value("Address", address.name, "modified")

		remove_link("Address", address.name, self.other_document.doctype, self.other_document.name)

		address.reload()
		self.assertEqual(len(address.links), 1)
		self.assertEqual(frappe.db.get_value("Address", address.name, "modified"), modified_before)

	def test_clears_the_documents_primary_link(self):
		address = self.create_address([self.link_to(self.document)])
		self.document.db_set({"primary_address": address.name, "primary_city": "_Test City"})

		remove_link("Address", address.name, self.document.doctype, self.document.name)

		self.document.reload()
		self.assertIsNone(self.document.primary_address)
		self.assertIsNone(self.document.primary_city)

	def test_keeps_a_primary_link_to_another_record(self):
		address = self.create_address([self.link_to(self.document)])
		other_address = self.create_address([self.link_to(self.document)])
		self.document.db_set("primary_address", other_address.name)

		remove_link("Address", address.name, self.document.doctype, self.document.name)

		self.document.reload()
		self.assertEqual(self.document.primary_address, other_address.name)

	def test_rejects_other_doctypes(self):
		with self.assertRaises(frappe.ValidationError):
			remove_link("ToDo", self.document.name, self.document.doctype, self.document.name)


class TestContactAddressPartyPermission(IntegrationTestCase):
	"""Contact/Address access follows the linked party (via `links`), using a
	throwaway DocType so this runs without ERPNext installed."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		cls.party_role = "Test Party Role"
		if not frappe.db.exists("Role", cls.party_role):
			frappe.get_doc({"doctype": "Role", "role_name": cls.party_role}).insert(ignore_permissions=True)

		# random suffix avoids clashing with a doctype an earlier run left behind
		cls.party_doctype = new_doctype(permissions=[{"role": cls.party_role, "read": 1}]).insert(
			ignore_permissions=True
		)
		cls.addClassCleanup(frappe.delete_doc, "DocType", cls.party_doctype.name, force=True)

		cls.original_party_doctypes = address_and_contact_module.PARTY_DOCTYPES
		address_and_contact_module.PARTY_DOCTYPES = (cls.party_doctype.name,)
		cls.addClassCleanup(
			setattr, address_and_contact_module, "PARTY_DOCTYPES", cls.original_party_doctypes
		)

		cls.party_a = cls.make_party("_Test Party A")
		cls.party_b = cls.make_party("_Test Party B")

		cls.scoped_user = "test_scoped_user@example.com"
		if not frappe.db.exists("User", cls.scoped_user):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": cls.scoped_user,
					"first_name": "Scoped",
					"send_welcome_email": 0,
					"roles": [{"role": cls.party_role}],
				}
			).insert(ignore_permissions=True)

		add_user_permission(cls.party_doctype.name, cls.party_a.name, cls.scoped_user)
		cls.addClassCleanup(remove_user_permission, cls.party_doctype.name, cls.party_a.name, cls.scoped_user)

	@classmethod
	def make_party(cls, some_fieldname):
		return frappe.get_doc({"doctype": cls.party_doctype.name, "some_fieldname": some_fieldname}).insert(
			ignore_permissions=True
		)

	def make_contact(self, party):
		return frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": f"_Test Contact for {party.name}",
				"links": [{"link_doctype": self.party_doctype.name, "link_name": party.name}],
			}
		).insert(ignore_permissions=True)

	def test_has_permission_follows_linked_party(self):
		contact_b = self.make_contact(self.party_b)
		contact_a = self.make_contact(self.party_a)

		self.assertFalse(has_permission(contact_b, "read", self.scoped_user))
		self.assertTrue(has_permission(contact_a, "read", self.scoped_user))

	def test_query_conditions_follow_linked_party(self):
		contact_b = self.make_contact(self.party_b)
		contact_a = self.make_contact(self.party_a)

		conditions = get_permission_query_conditions("Contact", self.scoped_user)
		names = frappe.db.sql_list(
			f"select name from `tabContact` where name in %(names)s and {conditions}",
			{"names": [contact_b.name, contact_a.name]},
		)

		self.assertIn(contact_a.name, names)
		self.assertNotIn(contact_b.name, names)

	def test_user_without_user_permission_sees_every_party(self):
		contact_b = self.make_contact(self.party_b)
		contact_a = self.make_contact(self.party_a)

		plain_user = "test_plain_user@example.com"
		if not frappe.db.exists("User", plain_user):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": plain_user,
					"first_name": "Plain",
					"send_welcome_email": 0,
					"roles": [{"role": self.party_role}],
				}
			).insert(ignore_permissions=True)

		self.assertTrue(has_permission(contact_b, "read", plain_user))
		self.assertTrue(has_permission(contact_a, "read", plain_user))

		conditions = get_permission_query_conditions("Contact", plain_user)
		names = frappe.db.sql_list(
			f"select name from `tabContact` where name in %(names)s and {conditions}",
			{"names": [contact_b.name, contact_a.name]},
		)
		self.assertIn(contact_a.name, names)
		self.assertIn(contact_b.name, names)

	def test_contact_without_party_link_is_always_visible(self):
		unlinked_contact = frappe.get_doc(
			{"doctype": "Contact", "first_name": "_Test Unlinked Contact"}
		).insert(ignore_permissions=True)

		self.assertTrue(has_permission(unlinked_contact, "read", self.scoped_user))

		conditions = get_permission_query_conditions("Contact", self.scoped_user)
		names = frappe.db.sql_list(
			f"select name from `tabContact` where name = %(name)s and {conditions}",
			{"name": unlinked_contact.name},
		)
		self.assertIn(unlinked_contact.name, names)

	def test_query_conditions_escape_backslash_in_party_name(self):
		"""A backslash in a party name must not break or bypass the condition."""
		# "Prompt" naming so the explicit backslash-containing name below actually
		# sticks; the shared self.party_doctype defaults to hash-based naming
		tricky_doctype = new_doctype(
			permissions=[{"role": self.party_role, "read": 1}], autoname="Prompt"
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "DocType", tricky_doctype.name, force=True)

		address_and_contact_module.PARTY_DOCTYPES = (self.party_doctype.name, tricky_doctype.name)
		self.addCleanup(setattr, address_and_contact_module, "PARTY_DOCTYPES", (self.party_doctype.name,))

		tricky_party = frappe.get_doc(
			{"doctype": tricky_doctype.name, "name": "_Test Tricky\\Party", "some_fieldname": "x"}
		).insert(ignore_permissions=True)
		self.assertEqual(tricky_party.name, "_Test Tricky\\Party")

		add_user_permission(tricky_doctype.name, tricky_party.name, self.scoped_user)
		self.addCleanup(remove_user_permission, tricky_doctype.name, tricky_party.name, self.scoped_user)

		allowed_contact = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": "_Test Contact for tricky party",
				"links": [{"link_doctype": tricky_doctype.name, "link_name": tricky_party.name}],
			}
		).insert(ignore_permissions=True)
		other_contact = self.make_contact(self.party_b)

		conditions = get_permission_query_conditions("Contact", self.scoped_user)
		names = frappe.db.sql_list(
			f"select name from `tabContact` where name in %(names)s and {conditions}",
			{"names": [allowed_contact.name, other_contact.name]},
		)
		self.assertIn(allowed_contact.name, names)
		self.assertNotIn(other_contact.name, names)
