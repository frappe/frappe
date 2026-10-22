import json

import frappe
from frappe.onboarding import update_onboarding_status, update_user_onboarding_status
from frappe.tests import IntegrationTestCase


class TestUserOnboardingStatus(IntegrationTestCase):
	def setUp(self):
		user = frappe.get_doc(
			doctype="User",
			email="onboarding-user@example.com",
			first_name="Onboarding",
			user_type="System User",
		).insert(ignore_if_duplicate=True, ignore_permissions=True)
		frappe.set_user(user.name)
		self.addCleanup(frappe.set_user, "Administrator")

	def saved_steps(self, app):
		status = frappe.db.get_value("User", frappe.session.user, "onboarding_status")
		return frappe.parse_json(status)[f"{app}_onboarding_status"]

	def test_saves_steps_for_an_app(self):
		steps = [{"name": "create_lead", "completed": True}]
		update_onboarding_status(json.dumps(steps), app="crm")
		self.assertEqual(self.saved_steps("crm"), steps)

	def test_the_old_name_still_saves(self):
		steps = [{"name": "create_deal", "completed": False}]
		update_user_onboarding_status(json.dumps(steps), appName="crm")
		self.assertEqual(self.saved_steps("crm"), steps)
