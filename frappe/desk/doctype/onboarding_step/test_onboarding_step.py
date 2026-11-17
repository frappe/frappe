# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.tests.utils import FrappeTestCase


class TestOnboardingStep(FrappeTestCase):
	def test_update_onboarding_step_only_updates_status_fields(self):
		from frappe.desk.desktop import update_onboarding_step

		step = frappe.get_doc(
			{"doctype": "Onboarding Step", "name": "Test Step", "title": "Test Step", "action": "Watch Video"}
		).insert(ignore_if_duplicate=True)
		self.addCleanup(frappe.delete_doc, "Onboarding Step", step.name, force=True)

		with self.set_user("test1@example.com"):
			update_onboarding_step(step.name, "title", "Changed")
			update_onboarding_step(step.name, "is_skipped", 1)

		self.assertEqual(frappe.db.get_value("Onboarding Step", step.name, "title"), "Test Step")
		self.assertEqual(frappe.db.get_value("Onboarding Step", step.name, "is_skipped"), 1)
