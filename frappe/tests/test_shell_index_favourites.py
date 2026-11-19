# The index boot's Favourites: the person's latest favourite records, lists and views they can still read.

from unittest.mock import patch

import frappe
from frappe.shell import SHELL_ROOT
from frappe.shell.boot import get_boot
from frappe.shell.index_favourites import MORE_LIMIT, index_favourites, more_favourites
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

	def favourite(self, doctype: str, name: str, user: str = USER, view: str = ""):
		"""Star the record, list or view for `user`, a minute after the previous star."""
		row = frappe.get_doc(
			doctype="Favourite", user=user, reference_doctype=doctype, reference_name=name, view=view
		).insert(ignore_permissions=True)
		self.minutes += 1
		starred = add_to_date(now_datetime(), minutes=self.minutes)
		frappe.db.set_value("Favourite", row.name, "creation", starred, update_modified=False)

	def favourites(self, user: str = USER) -> list[dict]:
		frappe.set_user(user)
		return get_boot(f"/{SHELL_ROOT}")["favourites"]

	def view(self, doctype: str = "ToDo", label: str = "Probe view", user: str = "") -> str:
		return (
			frappe.get_doc(
				doctype="Doctype View",
				reference_doctype=doctype,
				type="List",
				label=label,
				user=user,
				settings={},
			)
			.insert(ignore_permissions=True)
			.key
		)

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
				"kind": "record",
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

	def test_a_starred_list_is_a_chip_at_its_list_address(self):
		self.favourite("DocType", "ToDo")

		[chip] = self.favourites()

		self.assertEqual(
			{key: chip[key] for key in ("doctype", "name", "kind", "title", "route", "app")},
			{
				"doctype": "DocType",
				"name": "ToDo",
				"kind": "list",
				"title": "ToDo",
				"route": canonical_path("ToDo"),
				"app": "frappe",
			},
		)

	def test_a_starred_saved_view_is_a_chip_at_its_view_address(self):
		view = self.view(label="Probe open tasks")
		self.favourite("DocType", "ToDo", view=view)

		[chip] = self.favourites()

		self.assertEqual(
			{key: chip[key] for key in ("doctype", "name", "view", "kind", "title", "route")},
			{
				"doctype": "DocType",
				"name": "ToDo",
				"view": "probe-open-tasks",
				"kind": "view",
				"title": "Probe open tasks",
				"route": f"{canonical_path('ToDo')}/view/probe-open-tasks",
			},
		)

	def test_a_list_the_person_cannot_read_is_left_out(self):
		self.favourite("DocType", "Error Log")
		self.favourite("DocType", "ToDo")

		self.assertEqual([chip["name"] for chip in self.favourites()], ["ToDo"])
		self.assertEqual([chip["name"] for chip in self.favourites("Administrator")], [])

	def test_a_view_of_someone_else_or_of_an_unreadable_list_is_left_out(self):
		mine, site = self.view(label="Probe mine", user=USER), self.view(label="Probe site")
		theirs = self.view(label="Probe theirs", user="Administrator")
		private = self.view(doctype="Error Log", label="Probe errors")
		for key in (mine, site, theirs):
			self.favourite("DocType", "ToDo", view=key)
		self.favourite("DocType", "Error Log", view=private)

		self.assertEqual([chip["view"] for chip in self.favourites()], [site, mine])

	def test_records_lists_and_views_share_one_newest_first_order(self):
		todo, view = self.todo("Probe task", allocated_to=USER), self.view()
		self.favourite("ToDo", todo)
		self.favourite("DocType", "ToDo", view=view)
		self.favourite("DocType", "Note")

		self.assertEqual([chip["kind"] for chip in self.favourites()], ["list", "view", "record"])

	def test_eight_favourites_draw_no_more_chip_and_a_ninth_does(self):
		names = [self.todo(f"Probe task {number}", allocated_to=USER) for number in range(9)]
		for name in names[:8]:
			self.favourite("ToDo", name)
		frappe.set_user(USER)
		self.assertFalse(index_favourites()["more_favourites"])

		self.favourite("ToDo", names[8])
		self.assertTrue(index_favourites()["more_favourites"])

	def test_more_lists_the_rows_after_the_eighth_newest_first_with_the_same_checks(self):
		names = [self.todo(f"Probe task {number}", allocated_to=USER) for number in range(10)]
		hidden = self.todo("Probe task of someone else's")
		self.favourite("DocType", "Error Log")
		self.favourite("ToDo", hidden)
		self.favourite("DocType", "Note")
		for name in names:
			self.favourite("ToDo", name)
		frappe.set_user(USER)

		shown = [chip["name"] for chip in index_favourites()["favourites"]]
		more = [chip["name"] for chip in more_favourites()]

		self.assertEqual(shown, names[::-1][:8])
		self.assertEqual(more, [names[1], names[0], "Note"])

	def test_more_reads_at_most_fifty_rows(self):
		for number in range(8 + MORE_LIMIT + 1):
			self.favourite("ToDo", self.todo(f"Probe task {number}", allocated_to=USER))
		frappe.set_user(USER)

		self.assertEqual(len(more_favourites()), MORE_LIMIT)

	def test_more_refuses_a_website_user(self):
		website_user = "shell-favourites-website@example.com"
		if not frappe.db.exists("User", website_user):
			frappe.get_doc(
				doctype="User", email=website_user, first_name="Website", user_type="Website User"
			).insert(ignore_permissions=True)
		frappe.set_user(website_user)

		self.assertRaises(frappe.PermissionError, more_favourites)

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
			"frappe.shell.index_favourites.get_doctype_owners",
			return_value={"ToDo": "probe_app", "Note": "frappe"},
		):
			with patch(
				"frappe.shell.index_favourites.has_app_permission", side_effect=lambda app: app == "frappe"
			):
				self.assertEqual([row["doctype"] for row in index_favourites()["favourites"]], ["Note"])

	def test_a_list_or_view_in_an_app_the_person_cannot_enter_is_left_out(self):
		self.favourite("DocType", "ToDo")
		self.favourite("DocType", "ToDo", view=self.view())
		self.favourite("DocType", "Note")
		frappe.set_user(USER)

		with patch(
			"frappe.shell.index_favourites.get_doctype_owners",
			return_value={"ToDo": "probe_app", "Note": "frappe"},
		):
			with patch(
				"frappe.shell.index_favourites.has_app_permission", side_effect=lambda app: app == "frappe"
			):
				self.assertEqual([row["name"] for row in index_favourites()["favourites"]], ["Note"])

	def test_the_index_reads_favourites_in_one_query_plus_a_share_and_a_list_read_per_doctype(self):
		self.favourite("ToDo", self.todo("Probe task", allocated_to=USER))
		self.favourite("ToDo", self.todo("Probe task 2", allocated_to=USER))
		self.favourite("Note", self.note("Probe note"))
		frappe.set_user(USER)
		index_favourites()

		with self.assertQueryCount(5):
			self.assertEqual(len(index_favourites()["favourites"]), 3)

	def test_lists_cost_no_query_and_views_two_between_them(self):
		self.favourite("ToDo", self.todo("Probe task", allocated_to=USER))
		self.favourite("DocType", "ToDo")
		self.favourite("DocType", "Note")
		self.favourite("DocType", "ToDo", view=self.view(label="Probe one"))
		self.favourite("DocType", "Note", view=self.view(doctype="Note", label="Probe two"))
		frappe.set_user(USER)
		index_favourites()

		# The rows, then a share read and a row read for ToDo titles, and the same for the views.
		with self.assertQueryCount(5):
			self.assertEqual(len(index_favourites()["favourites"]), 5)
