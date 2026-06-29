# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.desk.doctype.onboarding_step.onboarding_step import get_onboarding_steps
from frappe.tests import IntegrationTestCase


class TestOnboardingStep(IntegrationTestCase):
	def test_get_onboarding_steps_accepts_native_list(self):
		step_name = "Native Onboarding Step " + frappe.generate_hash(length=6)
		step = frappe.get_doc(
			doctype="Onboarding Step",
			__newname=step_name,
			title=step_name,
			action="Go to Page",
			path="/app/todo",
		).insert(ignore_permissions=True)

		# ob_steps as a native list of dicts instead of a JSON string (frappe.parse_json passthrough)
		steps = get_onboarding_steps([{"step": step.name}])
		self.assertEqual(len(steps), 1)
		self.assertEqual(steps[0].name, step.name)
		step.delete()
