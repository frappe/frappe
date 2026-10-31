# The index boot's Recent: the person's last distinct v2 list, view and record addresses they can still open.

from datetime import datetime
from unittest.mock import patch

import frappe
from frappe.deferred_insert import save_to_db
from frappe.desk.doctype.route_history.route_history import deferred_insert, frequently_visited_links
from frappe.shell import SHELL_ROOT
from frappe.shell.boot import get_boot, index_recent
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, get_datetime, now_datetime
from frappe.utils.logging import get_log_db, log_table

ROLE = "Shell Recent Probe"
USER = "shell-recent-probe@example.com"
MANAGER = "shell-recent-manager-probe@example.com"


class TestIndexRecent(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.db.savepoint("index_recent_test")
		self.addCleanup(lambda: frappe.db.rollback(save_point="index_recent_test"))
		self.probe_user(USER, ROLE)
		self.probe_user(MANAGER, "System Manager")
		self.clear_visits()
		self.addCleanup(self.clear_visits)
		self.minutes = 0

	def probe_user(self, email: str, role: str):
		if not frappe.db.exists("Role", role):
			frappe.get_doc(doctype="Role", role_name=role, desk_access=1).insert()
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				doctype="User",
				email=email,
				first_name="Recent Probe",
				user_type="System User",
				send_welcome_email=0,
				roles=[{"role": role}],
			).insert()

	def clear_visits(self):
		qb, table = log_table("Route History")
		db = get_log_db()
		db.sql(qb.from_(table).where(table.user.isin([USER, MANAGER])).delete())
		db.commit()

	def visit(self, route: str, user: str = USER) -> datetime:
		"""Log a visit to `route`, a minute after the previous one, on the site's clock."""
		self.minutes += 1
		visited = add_to_date(now_datetime(), minutes=self.minutes)
		frappe.get_doc(doctype="Route History", route=route, user=user, creation=visited).db_insert()
		return visited

	def todo(self, description: str, allocated_to: str | None = USER) -> str:
		doc = frappe.get_doc(doctype="ToDo", description=description, allocated_to=allocated_to)
		return doc.insert(ignore_permissions=True).name

	def view(self, label: str, user: str = ""):
		frappe.get_doc(
			doctype="Doctype View", reference_doctype="ToDo", type="List", label=label, user=user, settings={}
		).insert(ignore_permissions=True)

	def recent(self, user: str = USER) -> list[dict]:
		frappe.set_user(user)
		return get_boot(f"/{SHELL_ROOT}")["recent"]

	def test_no_visits_is_an_empty_list(self):
		self.assertEqual(self.recent(), [])

	def test_the_five_latest_distinct_addresses_come_first_and_desk_v1_rows_are_skipped(self):
		names = [self.todo(f"Probe task {number}") for number in range(6)]
		for name in names:
			self.visit(f"/apps/desk/todo/{name}")
		self.visit(f"/apps/desk/todo/{names[1]}")
		self.visit(f"Form/ToDo/{names[0]}")

		self.assertEqual(
			[row["route"] for row in self.recent()],
			[f"/apps/desk/todo/{name}" for name in (names[1], names[5], names[4], names[3], names[2])],
		)

	def test_a_record_row_carries_its_title_kind_time_and_app(self):
		name = self.todo("Call Globex")
		visited = self.visit(f"/apps/desk/todo/{name}")

		[row] = self.recent()

		screen = frappe.get_hooks("add_to_apps_screen", app_name="frappe")[0]
		self.assertEqual(
			{**row, "visited": get_datetime(row["visited"])},
			{
				"route": f"/apps/desk/todo/{name}",
				"title": "Call Globex",
				"kind": "ToDo",
				"visited": visited,
				"app": "frappe",
				"app_title": frappe._(screen["title"]),
				"app_logo": screen.get("logo"),
			},
		)

	def test_a_list_row_is_titled_by_its_doctype(self):
		self.visit("/apps/desk/todo")

		[row] = self.recent()

		self.assertEqual((row["title"], row["kind"]), ("ToDo", "List"))

	def test_a_saved_view_row_is_titled_by_its_label(self):
		self.view("Probe open tasks")
		self.view("Probe their tasks", user=MANAGER)
		for key in ("probe-open-tasks", "probe-their-tasks", "no-such-view"):
			self.visit(f"/apps/desk/todo/view/{key}")

		[row] = self.recent()

		self.assertEqual(
			(row["route"], row["title"], row["kind"]),
			("/apps/desk/todo/view/probe-open-tasks", "Probe open tasks", "View"),
		)

	def test_a_single_is_titled_by_its_doctype_with_no_kind(self):
		self.visit("/apps/desk/system-settings/System%20Settings", user=MANAGER)

		[row] = self.recent(MANAGER)

		self.assertEqual((row["title"], row["kind"]), ("System Settings", None))

	def test_a_name_holding_a_slash_is_read_from_its_encoded_segment(self):
		name = (
			frappe.get_doc(doctype="Note", title="Probe/Slash", public=1).insert(ignore_permissions=True).name
		)
		self.visit(f"/apps/desk/note/{name.replace('/', '%2F')}")

		self.assertEqual([row["title"] for row in self.recent()], ["Probe/Slash"])

	def test_what_the_person_can_no_longer_open_is_left_out(self):
		mine = self.todo("Probe task of mine")
		theirs = self.todo("Probe task of someone else's", allocated_to=None)
		for route in (
			f"/apps/desk/todo/{mine}",
			f"/apps/desk/todo/{theirs}",
			"/apps/desk/role",
			"/apps/desk/system-settings/System%20Settings",
		):
			self.visit(route)

		self.assertEqual([row["route"] for row in self.recent()], [f"/apps/desk/todo/{mine}"])

	def test_an_address_in_an_app_the_person_cannot_enter_is_left_out(self):
		self.visit("/apps/desk/todo")
		frappe.set_user(USER)

		with patch("frappe.shell.boot.has_app_permission", return_value=False):
			self.assertEqual(index_recent(), [])

	def test_an_address_that_is_no_list_or_record_is_left_out(self):
		for route in (
			"/apps/no-such-prefix/todo",
			"/apps/desk/no-such-doctype",
			"/apps/desk/todo/view/list",
			"/apps/desk",
		):
			self.visit(route)

		self.assertEqual(self.recent(), [])

	def test_a_modular_app_reads_the_doctype_after_the_module(self):
		name = self.todo("Probe modular task")
		self.visit(f"/apps/desk/desk/todo/{name}")
		self.visit("/apps/desk/desk/todo")
		frappe.set_user(USER)

		with patch("frappe.shell.route_history.is_modular", return_value=True):
			self.assertEqual([row["kind"] for row in index_recent()], ["List", "ToDo"])

	def test_another_persons_visits_are_not_listed(self):
		self.visit("/apps/desk/todo", user=MANAGER)

		self.assertEqual(self.recent(), [])

	def test_a_visit_sent_through_the_deferred_insert_shows_on_the_index(self):
		name = self.todo("Probe sent task")
		frappe.set_user(USER)
		deferred_insert([{"route": f"/apps/desk/todo/{name}"}])
		frappe.set_user("Administrator")
		save_to_db("Route History")

		self.assertEqual([row["title"] for row in self.recent()], ["Probe sent task"])

	def test_desk_v1_frequent_links_leave_v2_addresses_out(self):
		self.visit("/apps/desk/todo")
		self.visit("List/ToDo")
		frappe.set_user(USER)

		self.assertEqual([link["route"] for link in frequently_visited_links()], ["List/ToDo"])

	def test_route_history_is_indexed_by_user(self):
		db = get_log_db()
		indexes = db.sql("SELECT name FROM sqlite_master WHERE type = 'index'", pluck=True)

		self.assertIn("tabRoute History_user_idx", indexes)

	def test_the_index_reads_titles_once_per_doctype(self):
		for name in (self.todo("Probe one"), self.todo("Probe two")):
			self.visit(f"/apps/desk/todo/{name}")
		note = frappe.get_doc(doctype="Note", title="Probe note", public=1).insert(ignore_permissions=True)
		self.visit(f"/apps/desk/note/{note.name}")
		self.visit("/apps/desk/todo")
		frappe.set_user(USER)
		index_recent()

		with self.assertQueryCount(4):
			self.assertEqual(len(index_recent()), 4)
