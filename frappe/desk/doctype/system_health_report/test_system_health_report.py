# Copyright (c) 2024, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.desk.form.load import getdoc
from frappe.tests.utils import FrappeTestCase


class TestSystemHealthReport(FrappeTestCase):
	def test_it_works(self):
		getdoc("System Health Report", "System Health Report")
