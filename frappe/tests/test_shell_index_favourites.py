# The index boot's Favourites: the person's latest favourite records they can still read.

from unittest.mock import patch

import frappe
from frappe.shell import SHELL_ROOT
from frappe.shell.boot import get_boot, index_favourites
from frappe.shell.links import canonical_path
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime

ROLE = "Shell Favourites Probe"
USER = "shell-favourites-probe@example.com"


class TestIndexFavourites(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.db.savepoint("index_favourites_test")
		self.addCleanup(lambda: frappe.db.rollback(save_point="index_favourites_test"))
		frappe.db.delete("Favourite", {"user": ("in", [USER, "Administrator"])})
		self.user = self.one_role_user()
		self.minutes = 0

	def one_role_user(self) -> str:
		if not frappe.db.exists("Role", ROLE):
			frappe.get_doc(doctype="Role", role_name=ROLE, desk_access=1).insert()

		if not frappe.db.exists("User", USER):
			frappe.get_doc(
				doctype="User",
				email=USER,
				first_name="Favourites Probe",
				user_type="System User",
				send_welcome_email=0,
				roles=[{"role": ROLE}],
			).insert()

		return USER

	def todo(self, description: str, allocated_to: str | None = None) -> str:
		doc = frappe.get_doc(doctype="ToDo", description=description, allocated_to=allocated_to)
		return doc.insert(ignore_permissions=True).name

	def favourite(self, doctype: str, name: str, user: str = USER):
		"""Star the record for `user`, a minute after the previous star."""
		row = frappe.get_doc(
			doctype="Favourite", user=user, reference_doctype=doctype, reference_name=name
		).insert(ignore_permissions=True)
		self.minutes += 1
		starred = add_to_date(now_datetime(), minutes=self.minutes)
		frappe.db.set_value("Favourite", row.name, "creation", starred, update_modified=False)

	def favourites(self, user: str = USER) -> list[dict]:
		frappe.set_user(user)
		return get_boot(f"/{SHELL_ROOT}")["favourites"]

	def test_no_favourites_is_an_empty_list(self):
		self.assertEqual(self.favourites(), [])

	def test_the_eight_newest_favourites_come_first_each_at_its_record_address(self):
		names = [self.todo(f"Probe task {number}", allocated_to=USER) for number in range(9)]
		for name in names:
			self.favourite("ToDo", name)

		favourites = self.favourites()

		self.assertEqual([row["name"] for row in favourites], names[::-1][:8])
		screen = frappe.get_hooks("add_to_apps_screen", app_name="frappe")[0]
		self.assertEqual(
			favourites[0],
			{
				"doctype": "ToDo",
				"name": names[-1],
				"title": "Probe task 8",
				"route": canonical_path("ToDo", names[-1]),
				"app": "frappe",
				"app_title": frappe._(screen["title"]),
				"app_logo": screen.get("logo"),
			},
		)

	def test_a_record_the_person_can_no_longer_read_is_left_out(self):
		mine = self.todo("Probe task of mine", allocated_to=USER)
		theirs = self.todo("Probe task of someone else's")
		for doctype, name in (("ToDo", mine), ("ToDo", theirs), ("Role", ROLE)):
			self.favourite(doctype, name)

		self.assertEqual([row["name"] for row in self.favourites()], [mine])

	def test_a_single_is_titled_by_its_doctype(self):
		self.favourite("System Settings", "System Settings", user="Administrator")

		[single] = self.favourites("Administrator")

		self.assertEqual(single["title"], "System Settings")
		self.assertEqual(single["route"], canonical_path("System Settings", "System Settings"))

	def test_another_persons_favourites_are_not_listed(self):
		self.favourite("ToDo", self.todo("Probe task", allocated_to=USER), user="Administrator")

		self.assertEqual(self.favourites(), [])

	def test_a_rich_text_title_is_drawn_as_plain_text(self):
		self.favourite("ToDo", self.todo("<p>Call &amp; plan</p>", allocated_to=USER))

		self.assertEqual(self.favourites()[0]["title"], "Call & plan")

	def note(self, title: str) -> str:
		return frappe.get_doc(doctype="Note", title=title, public=1).insert(ignore_permissions=True).name

	def test_favourites_of_several_doctypes_keep_their_order(self):
		first, second = (
			self.todo("Probe first", allocated_to=USER),
			self.todo("Probe third", allocated_to=USER),
		)
		note = self.note("Probe second")
		for doctype, name in (("ToDo", first), ("Note", note), ("ToDo", second)):
			self.favourite(doctype, name)

		self.assertEqual(
			[(row["doctype"], row["title"]) for row in self.favourites()],
			[("ToDo", "Probe third"), ("Note", "Probe second"), ("ToDo", "Probe first")],
		)

	def test_a_record_outside_the_persons_user_permissions_is_left_out(self):
		allowed, other = self.note("Probe allowed"), self.note("Probe other")
		for name in (allowed, other):
			self.favourite("Note", name)
		frappe.get_doc(doctype="User Permission", user=USER, allow="Note", for_value=allowed).insert(
			ignore_permissions=True
		)

		self.assertEqual([row["name"] for row in self.favourites()], [allowed])

	def test_a_single_the_person_cannot_read_is_left_out(self):
		self.favourite("System Settings", "System Settings")

		self.assertEqual(self.favourites(), [])

	def test_a_record_in_an_app_the_person_cannot_enter_is_left_out(self):
		self.favourite("ToDo", self.todo("Probe task", allocated_to=USER))
		self.favourite("Note", self.note("Probe note"))
		frappe.set_user(USER)

		with patch(
			"frappe.shell.boot.get_doctype_owners", return_value={"ToDo": "probe_app", "Note": "frappe"}
		):
			with patch("frappe.shell.boot.has_app_permission", side_effect=lambda app: app == "frappe"):
				self.assertEqual([row["doctype"] for row in index_favourites()], ["Note"])

	def test_the_index_reads_favourites_in_one_query_plus_a_share_and_a_list_read_per_doctype(self):
		self.favourite("ToDo", self.todo("Probe task", allocated_to=USER))
		self.favourite("ToDo", self.todo("Probe task 2", allocated_to=USER))
		self.favourite("Note", self.note("Probe note"))
		frappe.set_user(USER)
		index_favourites()

		with self.assertQueryCount(5):
			self.assertEqual(len(index_favourites()), 3)
