# Copyright (c) 2024, Frappe Technologies and Contributors
# See license.txt

import frappe
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase
=======
from frappe.desk.form.load import getdoc
from frappe.tests import IntegrationTestCase
>>>>>>> 2f50f3174f (fix(desk): guard owner/modified_by access in update_user_info (#35581))


class TestSystemHealthReport(FrappeTestCase):
	def test_it_works(self):
		getdoc("System Health Report", "System Health Report")
