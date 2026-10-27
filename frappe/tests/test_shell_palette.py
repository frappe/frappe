# The palette's places: the doctypes a person can read, with their address and create right, and their apps.

from unittest.mock import patch

import frappe
from frappe.permissions import add_permission, update_permission_property
from frappe.shell import SHELL_ROOT
from frappe.shell.links import canonical_path
from frappe.shell.palette import places
from frappe.tests import IntegrationTestCase

ROLE = "Shell Palette Probe"
USER = "shell-palette-probe@example.com"


class TestPalettePlaces(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.db.savepoint("palette_places_test")
		self.addCleanup(lambda: frappe.clear_cache(doctype="Role"))
		self.addCleanup(lambda: frappe.db.rollback(save_point="palette_places_test"))
		self.one_role_user()

	def one_role_user(self):
		if not frappe.db.exists("Role", ROLE):
			frappe.get_doc(doctype="Role", role_name=ROLE, desk_access=1).insert()
		if not frappe.db.exists("User", USER):
			frappe.get_doc(
				doctype="User",
				email=USER,
				first_name="Palette Probe",
				user_type="System User",
				send_welcome_email=0,
				roles=[{"role": ROLE}],
			).insert()

	def places_of(self, user: str) -> dict:
		frappe.set_user(user)
		return places()

	def test_a_one_role_user_gets_only_the_doctypes_their_role_reads(self):
		before = {row["name"] for row in self.places_of(USER)["doctypes"]}
		frappe.set_user("Administrator")
		add_permission("Role", ROLE)
		frappe.clear_cache(doctype="Role")

		doctypes = {row["name"]: row for row in self.places_of(USER)["doctypes"]}

		self.assertEqual(set(doctypes) - before, {"Role"})
		self.assertEqual(
			doctypes["Role"],
			{"name": "Role", "app": "frappe", "route": canonical_path("Role"), "can_create": False},
		)
		self.assertNotIn("DocType", doctypes)
		self.assertNotIn("System Settings", doctypes)

	def test_a_doctype_of_an_app_the_user_may_not_enter_is_left_out(self):
		add_permission("Role", ROLE)
		frappe.clear_cache(doctype="Role")

		with patch("frappe.shell.palette.has_app_permission", lambda app: app != "frappe"):
			doctypes = {row["name"] for row in self.places_of(USER)["doctypes"]}

		self.assertNotIn("Role", doctypes)

	def test_the_create_right_comes_with_the_role(self):
		add_permission("Role", ROLE)
		update_permission_property("Role", ROLE, 0, "create", 1)
		frappe.clear_cache(doctype="Role")

		doctypes = {row["name"]: row for row in self.places_of(USER)["doctypes"]}

		self.assertTrue(doctypes["Role"]["can_create"])

	def test_administrator_gets_every_doctype_a_single_at_its_record_and_the_apps(self):
		reply = self.places_of("Administrator")
		doctypes = {row["name"]: row for row in reply["doctypes"]}

		self.assertTrue(doctypes["DocType"]["can_create"])
		self.assertEqual(
			doctypes["System Settings"]["route"], canonical_path("System Settings", "System Settings")
		)
		self.assertFalse(doctypes["System Settings"]["can_create"])
		self.assertNotIn("DocField", doctypes)
		self.assertEqual(list(doctypes), sorted(doctypes))

		frappe_app = next(app for app in reply["apps"] if app["app"] == "frappe")
		self.assertTrue(frappe_app["route"].startswith(f"/{SHELL_ROOT}/"))
		self.assertIn("frappe", reply["titles"])

	def test_a_guest_is_refused(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			places()
