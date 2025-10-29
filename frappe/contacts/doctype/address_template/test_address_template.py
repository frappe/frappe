# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.contacts.doctype.address_template.address_template import get_default_address_template
from frappe.tests import IntegrationTestCase
from frappe.utils.jinja import validate_template


class TestAddressTemplate(IntegrationTestCase):
	def setUp(self) -> None:
		frappe.db.delete("Address Template", {"country": "India"})
		frappe.db.delete("Address Template", {"country": "Brazil"})

	def test_default_address_template(self):
		validate_template(get_default_address_template())

	def test_default_is_unset(self):
		frappe.get_doc({"doctype": "Address Template", "country": "India", "is_default": 1}).insert()

		self.assertEqual(frappe.db.get_value("Address Template", "India", "is_default"), 1)

		frappe.get_doc({"doctype": "Address Template", "country": "Brazil", "is_default": 1}).insert()

		self.assertEqual(frappe.db.get_value("Address Template", "India", "is_default"), 0)
		self.assertEqual(frappe.db.get_value("Address Template", "Brazil", "is_default"), 1)

	def test_delete_address_template(self):
		india = frappe.get_doc({"doctype": "Address Template", "country": "India", "is_default": 0}).insert()

		brazil = frappe.get_doc(
			{"doctype": "Address Template", "country": "Brazil", "is_default": 1}
		).insert()

		india.reload()  # might have been modified by the second template
		india.delete()  # should not raise an error

		self.assertRaises(frappe.ValidationError, brazil.delete)
