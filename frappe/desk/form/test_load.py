# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from unittest.mock import patch

from frappe.core.doctype.communication.communication import parse_email
from frappe.desk.form.load import get_document_email
from frappe.tests import IntegrationTestCase


class TestLoad(IntegrationTestCase):
	def test_get_document_email(self):
		with patch(
			"frappe.email.doctype.email_account.email_account.get_automatic_email_link",
			return_value="erpnext@example.com",
		):
			address = get_document_email("Purchase Order", "PO-26465-002")
			address_with_separator_in_name = get_document_email("Purchase Order", "PO/2026/002")

		self.assertEqual(address, "erpnext+Purchase%20Order=PO-26465-002@example.com")
		self.assertEqual(
			address_with_separator_in_name, "erpnext+Purchase%20Order=PO%2F2026%2F002@example.com"
		)
		self.assertEqual([("Purchase Order", "PO-26465-002")], list(parse_email([address])))
		self.assertEqual(
			[("Purchase Order", "PO/2026/002")], list(parse_email([address_with_separator_in_name]))
		)
