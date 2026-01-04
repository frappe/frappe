# Copyright (c) 2024, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.desk.form.load import getdoc
from frappe.tests import IntegrationTestCase


class TestSystemHealthReport(IntegrationTestCase):
	def test_it_works(self):
		getdoc("System Health Report", "System Health Report")
