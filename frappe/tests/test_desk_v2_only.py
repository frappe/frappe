# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import importlib
import pkgutil

import frappe
import frappe.shell
from frappe.core.doctype.user.user import generate_keys
from frappe.tests import IntegrationTestCase
from frappe.tests.test_api import FrappeAPITestCase

DESK_USER = "desk-v2-only-user@example.com"
SHELL_ONLY = "frappe.email.inbox.get_outgoing_senders"
FRAMEWORK_UI = "frappe.onboarding.update_onboarding_status"


class TestDeskV2OnlyMethods(FrappeAPITestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("User", DESK_USER):
			frappe.get_doc(doctype="User", email=DESK_USER, first_name="Desk", send_welcome_email=0).insert(
				ignore_permissions=True
			)
		frappe.get_doc("User", DESK_USER).add_roles("Desk User")
		api_secret = generate_keys(DESK_USER)["api_secret"]
		api_key = frappe.db.get_value("User", DESK_USER, "api_key")
		cls.auth = {"Authorization": f"token {api_key}:{api_secret}"}
		frappe.db.commit()

	def call(self, method: str):
		if method == FRAMEWORK_UI:
			return self.post(self.method(method), {"steps": "[]", "app": "frappe"}, headers=self.auth)
		return self.get(self.method(method), headers=self.auth)

	def test_switch_off_refuses_shell_only_methods(self):
		with self.change_settings("System Settings", commit=True, enable_desk_v2=0):
			response = self.call(SHELL_ONLY)
			self.assertEqual(response.status_code, 403)
			self.assertEqual(response.json["exc_type"], "DeskV2DisabledError")
			self.assertEqual(self.call(FRAMEWORK_UI).status_code, 200)

	def test_switch_on_answers_both(self):
		with self.change_settings("System Settings", commit=True, enable_desk_v2=1):
			self.assertEqual(self.call(SHELL_ONLY).status_code, 200)
			self.assertEqual(self.call(FRAMEWORK_UI).status_code, 200)


class TestDeskV2OnlyDecorator(IntegrationTestCase):
	def test_must_sit_above_whitelist(self):
		def method():
			pass

		self.assertRaises(TypeError, frappe.desk_v2_only, method)

	def test_every_shell_method_is_gated(self):
		for module in pkgutil.walk_packages(frappe.shell.__path__, "frappe.shell."):
			importlib.import_module(module.name)

		open_shell_methods = [
			f"{fn.__module__}.{fn.__qualname__}"
			for fn in frappe.whitelisted
			if fn.__module__.startswith("frappe.shell.") and fn not in frappe.desk_v2_methods
		]
		self.assertEqual(open_shell_methods, [])
