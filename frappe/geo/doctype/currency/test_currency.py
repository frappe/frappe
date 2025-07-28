# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

# pre loaded

import frappe
from frappe.tests import IntegrationTestCase


class TestUser(IntegrationTestCase):
	def test_default_currency_on_setup(self):
		usd = frappe.get_doc("Currency", "USD")
		self.assertDocumentEqual({"enabled": 1, "fraction": "Cent"}, usd)
