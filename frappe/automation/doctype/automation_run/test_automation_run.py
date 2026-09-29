# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.automation.doctype.automation_run.automation_run import AutomationRun
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, now


def make_run(status, days_old=0):
	run = frappe.get_doc(
		{
			"doctype": "Automation Run",
			"automation_title": "Cleanup",
			"status": status,
			"steps": [{"step_idx": 0, "action_type": "SetFieldValue", "status": "Success"}],
		}
	).insert(ignore_permissions=True)
	frappe.db.set_value("Automation Run", run.name, "creation", add_days(now(), -days_old))
	return run.name


class IntegrationTestAutomationRun(IntegrationTestCase):
	def test_clear_old_logs_keeps_recent_and_waiting_runs(self):
		old = make_run("Success", days_old=40)
		waiting = make_run("Waiting", days_old=40)
		recent = make_run("Success")

		AutomationRun.clear_old_logs(days=30)

		self.assertFalse(frappe.db.exists("Automation Run", old))
		self.assertFalse(frappe.db.exists("Automation Run Step", {"parent": old}))
		self.assertTrue(frappe.db.exists("Automation Run", waiting))
		self.assertTrue(frappe.db.exists("Automation Run Step", {"parent": waiting}))
		self.assertTrue(frappe.db.exists("Automation Run", recent))
