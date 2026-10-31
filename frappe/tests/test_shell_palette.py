# The palette's places: the doctypes a person can read, with their address and create right, their apps,
# and their recent visits.

from unittest.mock import patch

import frappe
from frappe.permissions import add_permission, update_permission_property
from frappe.shell import SHELL_ROOT
from frappe.shell.boot import app_screen
from frappe.shell.links import canonical_path
from frappe.shell.palette import places
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime
from frappe.utils.logging import get_log_db, log_table

ROLE = "Shell Palette Probe"
USER = "shell-palette-probe@example.com"
MANAGER = "shell-palette-manager-probe@example.com"


class TestPalettePlaces(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.db.savepoint("palette_places_test")
		self.addCleanup(lambda: frappe.clear_cache(doctype="Role"))
		self.addCleanup(lambda: frappe.db.rollback(save_point="palette_places_test"))
		self.one_role_user()
		self.probe_user(MANAGER, "System Manager")
		self.clear_visits()
		self.addCleanup(self.clear_visits)
		self.minutes = 0
		self.start = now_datetime()

	def one_role_user(self):
		if not frappe.db.exists("Role", ROLE):
			frappe.get_doc(doctype="Role", role_name=ROLE, desk_access=1).insert()
		self.probe_user(USER, ROLE)

	def probe_user(self, email: str, role: str):
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				doctype="User",
				email=email,
				first_name="Palette Probe",
				user_type="System User",
				send_welcome_email=0,
				roles=[{"role": role}],
			).insert()

	def clear_visits(self):
		qb, table = log_table("Route History")
		db = get_log_db()
		db.sql(qb.from_(table).where(table.user.isin([USER, MANAGER])).delete())
		db.commit()

	def visit(self, route: str, user: str = USER):
		"""Log a visit to `route`, a minute after the previous one."""
		self.minutes += 1
		visited = add_to_date(self.start, minutes=self.minutes)
		frappe.get_doc(doctype="Route History", route=route, user=user, creation=visited).db_insert()

	def todo(self, description: str) -> str:
		doc = frappe.get_doc(doctype="ToDo", description=description, allocated_to=USER)
		return doc.insert(ignore_permissions=True).name

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

	def test_recent_holds_the_users_own_visits_titled_newest_first(self):
		name = self.todo("Call Globex")
		self.visit(f"/{SHELL_ROOT}/desk/todo/{name}")
		self.visit(f"/{SHELL_ROOT}/desk/todo")
		self.visit(f"/{SHELL_ROOT}/desk/note", user=MANAGER)

		recent = self.places_of(USER)["recent"]

		desk = app_screen("frappe")["title"]
		self.assertEqual(
			[{key: value for key, value in row.items() if key != "visited"} for row in recent],
			[
				{
					"route": f"/{SHELL_ROOT}/desk/todo",
					"doctype": "ToDo",
					"name": None,
					"view": None,
					"title": "ToDo",
					"kind": "list",
					"description": desk,
				},
				{
					"route": f"/{SHELL_ROOT}/desk/todo/{name}",
					"doctype": "ToDo",
					"name": name,
					"view": None,
					"title": "Call Globex",
					"kind": "record",
					"description": "ToDo",
				},
			],
		)
		self.assertEqual(recent[0]["visited"] - recent[1]["visited"], 60_000)

	def test_recent_leaves_out_a_record_the_user_cannot_read(self):
		theirs = frappe.get_doc(doctype="ToDo", description="Someone else's task", allocated_to=MANAGER)
		theirs.insert(ignore_permissions=True)
		self.visit(f"/{SHELL_ROOT}/desk/todo/{theirs.name}")

		self.assertEqual(self.places_of(USER)["recent"], [])

	def test_recent_leaves_out_a_doctype_the_user_cannot_read(self):
		self.visit(f"/{SHELL_ROOT}/desk/role")
		self.assertEqual(self.places_of(USER)["recent"], [])

		frappe.set_user("Administrator")
		add_permission("Role", ROLE)
		frappe.clear_cache(doctype="Role")

		self.assertEqual(
			[row["route"] for row in self.places_of(USER)["recent"]], [f"/{SHELL_ROOT}/desk/role"]
		)

	def test_recent_holds_a_single_by_its_doctype_and_app(self):
		self.visit(f"/{SHELL_ROOT}/desk/system-settings/System%20Settings", user=MANAGER)

		[row] = self.places_of(MANAGER)["recent"]

		self.assertEqual(
			(row["doctype"], row["name"], row["title"], row["kind"], row["description"]),
			(
				"System Settings",
				"System Settings",
				"System Settings",
				"record",
				app_screen("frappe")["title"],
			),
		)
