# The index boot's "Get more apps" link: only where Cloud Settings would let the person install an app.

from unittest.mock import patch

import frappe
from frappe.shell import SHELL_ROOT
from frappe.shell.boot import CLOUD_SETTINGS_ROUTE, get_boot
from frappe.tests import IntegrationTestCase

PILOT = {"pilot_endpoint": "https://pilot.example.com", "pilot_auth_token": "site-token"}
ROLE = "Shell More Apps Probe"
USER = "shell-more-apps-probe@example.com"


class TestIndexMoreApps(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.db.savepoint("index_more_apps_test")
		self.addCleanup(lambda: frappe.db.rollback(save_point="index_more_apps_test"))

	def more_apps(self, conf: dict, user: str = "Administrator") -> str | None:
		frappe.set_user(user)
		with patch.dict(frappe.conf, {"pilot_endpoint": None, "pilot_auth_token": None, **conf}):
			return get_boot(f"/{SHELL_ROOT}")["more_apps"]

	def test_a_system_manager_on_a_cloud_site_gets_the_link(self):
		self.assertEqual(self.more_apps(PILOT), CLOUD_SETTINGS_ROUTE)

	def test_a_self_hosted_site_has_none(self):
		self.assertIsNone(self.more_apps({}))

	def test_an_endpoint_without_its_token_is_not_enough(self):
		self.assertIsNone(self.more_apps({"pilot_endpoint": PILOT["pilot_endpoint"]}))

	def test_a_user_who_is_not_a_system_manager_has_none(self):
		self.assertIsNone(self.more_apps(PILOT, user=self.one_role_user()))

	def one_role_user(self) -> str:
		if not frappe.db.exists("Role", ROLE):
			frappe.get_doc(doctype="Role", role_name=ROLE, desk_access=1).insert()

		if not frappe.db.exists("User", USER):
			frappe.get_doc(
				doctype="User",
				email=USER,
				first_name="More Apps Probe",
				user_type="System User",
				send_welcome_email=0,
				roles=[{"role": ROLE}],
			).insert()

		return USER
