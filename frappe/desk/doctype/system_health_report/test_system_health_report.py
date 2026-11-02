# Copyright (c) 2024, Frappe Technologies and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.desk.form.load import getdoc
from frappe.tests import IntegrationTestCase


class TestSystemHealthReport(IntegrationTestCase):
	def test_it_works(self):
		getdoc("System Health Report", "System Health Report")

	def test_permission_check_does_not_load_report(self):
		frappe.get_doc("User", "test1@example.com").add_roles("System Manager")

		with self.set_user("test1@example.com"), patch("frappe.enqueue") as enqueue:
			self.assertTrue(frappe.has_permission("System Health Report"))

		enqueue.assert_not_called()
