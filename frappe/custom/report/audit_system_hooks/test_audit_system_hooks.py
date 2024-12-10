# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt


from frappe.custom.report.audit_system_hooks.audit_system_hooks import execute
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase


class TestAuditSystemHooksReport(FrappeTestCase):
=======
from frappe.tests import IntegrationTestCase


class TestAuditSystemHooksReport(IntegrationTestCase):
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	def test_basic_query(self):
		_, data = execute()
		for row in data:
			if row.get("hook_name") == "app_name":
				self.assertEqual(row.get("hook_values"), "frappe")
				break
		else:
			self.fail("Failed to generate hooks report")
