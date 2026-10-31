# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.desk.doctype.doctype_view import api
from frappe.desk.doctype.doctype_view.api import find, get, reset, save
from frappe.desk.doctype.doctype_view.key_space import KeySpace
from frappe.desk.doctype.favourite.favourite import toggle_favourite
from frappe.exceptions import FrappeTypeError
from frappe.query_builder.utils import db_type_is
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user
from frappe.tests.test_query_builder import run_only_if

# A doctype every Desk User reads, and one only a System Manager reads.
DOCTYPE = "Note"
PRIVATE_DOCTYPE = "System Settings"

PERSON = "test_view_person@example.com"
OTHER = "test_view_other@example.com"
MANAGER = "test_view_manager@example.com"


def a_person(email: str, role: str = "Desk User") -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			doctype="User",
			email=email,
			first_name="Viewer",
			user_type="System User",
			roles=[{"role": role}],
		).insert(ignore_permissions=True)

	return email


def make_view(**kwargs):
	return frappe.get_doc({"doctype": "Doctype View", "reference_doctype": DOCTYPE, "type": "List", **kwargs})


class DoctypeViewTestCase(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		# The class rolls back once, so each test starts from no rows of its own.
		frappe.db.delete("Doctype View", {"reference_doctype": DOCTYPE})
		self.person = a_person(PERSON)
		self.other = a_person(OTHER)
		self.manager = a_person(MANAGER, role="System Manager")


class TestDoctypeView(DoctypeViewTestCase):
	def test_a_blank_user_and_label_are_stored_as_blank(self):
		doc = make_view(settings={"sort": []}).insert()

		self.assertEqual(frappe.db.get_value("Doctype View", doc.name, ["user", "label"]), ("", ""))

	def test_a_second_row_at_one_address_is_refused_cleanly(self):
		make_view(settings={}).insert()

		self.assertRaisesRegex(
			frappe.ValidationError, "already has a List view", make_view(settings={}).insert
		)

	def test_an_unknown_type_is_refused(self):
		self.assertRaisesRegex(frappe.ValidationError, "not a view type", make_view(type="Kanban").insert)

	def test_settings_are_one_object(self):
		self.assertRaisesRegex(frappe.ValidationError, "one object", make_view(settings=["columns"]).insert)

	def test_settings_are_capped(self):
		self.assertRaisesRegex(
			frappe.ValidationError, "larger than", make_view(settings={"note": "x" * 20_000}).insert
		)

	def test_settings_that_are_not_json_are_refused(self):
		self.assertRaisesRegex(frappe.ValidationError, "one object", make_view(settings="not json").insert)

	def test_the_document_gate_lets_a_person_read_the_site_row_and_write_only_their_own(self):
		site = make_view(settings={}).insert()
		own = make_view(user=self.person, settings={}).insert()
		other = make_view(user=self.other, settings={}).insert()

		self.assertTrue(frappe.has_permission("Doctype View", "read", site, user=self.person))
		self.assertTrue(frappe.has_permission("Doctype View", "read", own, user=self.person))
		self.assertFalse(frappe.has_permission("Doctype View", "read", other, user=self.person))
		self.assertFalse(frappe.has_permission("Doctype View", "write", site, user=self.person))
		self.assertTrue(frappe.has_permission("Doctype View", "read", other, user=self.manager))

	def test_a_person_reads_the_site_row_and_their_own_and_nothing_else(self):
		make_view(settings={}).insert()
		make_view(user=self.person, settings={}).insert()
		make_view(user=self.other, settings={}).insert()

		with set_user(self.person):
			seen = frappe.get_list("Doctype View", filters={"reference_doctype": DOCTYPE}, pluck="user")

		self.assertEqual(sorted(seen), ["", self.person])


class TestApi(DoctypeViewTestCase):
	def test_nothing_stored_reads_as_two_absences(self):
		with set_user(self.person):
			self.assertEqual(
				get(DOCTYPE), {"site": None, "user": None, "favourites": {"list": False, "views": []}}
			)

	def test_a_save_patches_keys_on_the_caller_s_own_row(self):
		with set_user(self.person):
			save(DOCTYPE, "List", "user", {"columns": [{"fieldname": "title"}]})
			rows = save(DOCTYPE, "List", "user", {"sort": [{"fieldname": "title", "direction": "asc"}]})

		self.assertEqual(
			rows["user"],
			{"columns": [{"fieldname": "title"}], "sort": [{"fieldname": "title", "direction": "asc"}]},
		)
		self.assertIsNone(rows["site"])
		self.assertEqual(
			frappe.db.get_value("Doctype View", {"reference_doctype": DOCTYPE}, "user"), self.person
		)

	def test_a_first_save_that_loses_the_race_lands_on_the_twin_s_row(self):
		"""Two first saves can both see no row; the loser's insert hits the index and runs again."""
		real = api._locked
		reads = []

		def racing(address):
			reads.append(address)
			return (None, {}) if len(reads) == 1 else real(address)

		with set_user(self.person):
			save(DOCTYPE, "List", "user", {"columns": []})
			with patch.object(api, "_locked", side_effect=racing):
				rows = save(DOCTYPE, "List", "user", {"sort": []})

		self.assertEqual(len(reads), 2)
		self.assertEqual(rows["user"], {"columns": [], "sort": []})

	def test_a_reset_clears_one_key_and_drops_an_empty_row(self):
		with set_user(self.person):
			save(DOCTYPE, "List", "user", {"columns": [], "sort": []})
			rows = reset(DOCTYPE, "List", "user", "columns")
			self.assertEqual(rows["user"], {"sort": []})

			rows = reset(DOCTYPE, "List", "user", "sort")

		self.assertIsNone(rows["user"])
		self.assertFalse(frappe.db.exists("Doctype View", {"reference_doctype": DOCTYPE}))

	def test_the_site_scope_needs_a_system_manager(self):
		with set_user(self.person):
			self.assertRaises(frappe.PermissionError, save, DOCTYPE, "List", "site", {"sort": []})

		with set_user(self.manager):
			rows = save(DOCTYPE, "List", "site", {"sort": []})

		self.assertEqual(rows["site"], {"sort": []})
		self.assertEqual(frappe.db.get_value("Doctype View", {"reference_doctype": DOCTYPE}, "user"), "")

	def test_everyone_reads_the_site_row_beside_their_own(self):
		with set_user(self.manager):
			save(DOCTYPE, "List", "site", {"sort": []})

		with set_user(self.person):
			save(DOCTYPE, "List", "user", {"columns": []})
			self.assertEqual(
				get(DOCTYPE),
				{"site": {"sort": []}, "user": {"columns": []}, "favourites": {"list": False, "views": []}},
			)

		with set_user(self.other):
			self.assertEqual(
				get(DOCTYPE), {"site": {"sort": []}, "user": None, "favourites": {"list": False, "views": []}}
			)

	def test_a_doctype_the_caller_cannot_read_is_refused(self):
		with set_user(self.person):
			self.assertRaises(frappe.PermissionError, get, PRIVATE_DOCTYPE)

	def test_the_read_says_which_of_the_list_and_its_views_the_caller_starred(self):
		make_view(label="Open notes", settings={}).insert()
		make_view(label="Closed notes", settings={}).insert()
		with set_user(self.person):
			toggle_favourite("DocType", DOCTYPE, add=True)
			toggle_favourite("DocType", DOCTYPE, add=True, view="open-notes")
			self.assertEqual(get(DOCTYPE)["favourites"], {"list": True, "views": ["open-notes"]})

		with set_user(self.other):
			toggle_favourite("DocType", DOCTYPE, add=True, view="closed-notes")
			self.assertEqual(get(DOCTYPE)["favourites"], {"list": False, "views": ["closed-notes"]})

	def test_a_starred_view_of_another_doctype_is_not_this_list_s(self):
		make_view(reference_doctype="ToDo", label="Elsewhere", settings={}).insert()
		with set_user(self.person):
			toggle_favourite("DocType", "ToDo", add=True, view="elsewhere")
			toggle_favourite("DocType", "ToDo", add=True)
			self.assertEqual(get(DOCTYPE)["favourites"], {"list": False, "views": []})

	def test_a_bad_argument_is_refused_before_anything_is_read(self):
		with set_user(self.person):
			self.assertRaises(frappe.ValidationError, get, "No Such Doctype")
			self.assertRaises(frappe.ValidationError, get, DOCTYPE, "Kanban")
			self.assertRaises(frappe.ValidationError, save, DOCTYPE, "List", "everyone", {})
			self.assertRaises(FrappeTypeError, save, DOCTYPE, "List", "user", "not json")
			self.assertRaises(FrappeTypeError, save, DOCTYPE, "List", "user", ["a list"])
			self.assertRaises(FrappeTypeError, reset, DOCTYPE, "List", "user", ["a list"])


class TestViewKey(DoctypeViewTestCase):
	def test_a_saved_view_s_key_is_its_label_made_url_safe(self):
		self.assertEqual(
			make_view(label="Open Deals: Café & Co.", settings={}).insert().key, "open-deals-cafe-co"
		)

	def test_a_label_with_no_latin_letters_gets_a_short_random_key(self):
		key = make_view(label="खुले सौदे", settings={}).insert().key

		self.assertRegex(key, r"^[a-z0-9]{8}$")

	def test_the_plain_view_has_no_key(self):
		self.assertEqual(make_view(settings={}).insert().key, "")

	def test_a_taken_key_gets_the_next_free_suffix(self):
		keys = [make_view(label="Open", settings={}).insert().key for _ in range(2)]
		keys.append(make_view(label="open!", user=self.person, settings={}).insert().key)

		self.assertEqual(keys, ["open", "open-2", "open-3"])

	def test_a_view_type_name_is_never_a_key(self):
		keys = [make_view(label=label, settings={}).insert().key for label in ("List", "Kanban")]

		self.assertEqual(keys, ["list-2", "kanban-2"])

	def test_one_person_s_key_is_taken_for_every_other_person_and_the_site(self):
		mine = make_view(label="Mine", user=self.person, settings={}).insert()
		theirs = make_view(label="Mine", user=self.other, settings={}).insert()
		site = make_view(label="Mine", settings={}).insert()

		self.assertEqual([mine.key, theirs.key, site.key], ["mine", "mine-2", "mine-3"])

	def test_a_new_label_keeps_the_key(self):
		view = make_view(label="Open", settings={}).insert()
		view.label = "Closed"
		view.save()

		self.assertEqual(frappe.db.get_value("Doctype View", view.name, "key"), "open")

	def test_the_key_cannot_be_changed(self):
		view = make_view(label="Open", settings={}).insert()
		view.key = "elsewhere"

		self.assertRaises(frappe.CannotChangeConstantError, view.save)

	def test_two_views_may_share_a_label(self):
		make_view(label="Open", user=self.person, settings={}).insert()
		make_view(label="Open", user=self.person, settings={}).insert()

		self.assertEqual(frappe.db.count("Doctype View", {"reference_doctype": DOCTYPE, "label": "Open"}), 2)

	def test_a_new_view_locks_its_doctype_while_it_claims_a_key(self):
		with patch("frappe.db.get_value", wraps=frappe.db.get_value) as get_value:
			make_view(label="Open", settings={}).insert()

		get_value.assert_any_call("DocType", DOCTYPE, "name", for_update=True)

	def test_a_label_cannot_turn_the_plain_view_into_a_saved_one_or_back(self):
		plain = make_view(settings={}).insert()
		saved = make_view(label="Open", settings={}).insert()

		plain.label = "Now named"
		self.assertRaisesRegex(frappe.ValidationError, "plain view cannot have one", plain.save)
		saved.label = ""
		self.assertRaisesRegex(frappe.ValidationError, "needs a label", saved.save)


@run_only_if(db_type_is.MARIADB)
class TestKeyRace(IntegrationTestCase):
	# Its own class: rows the other tests wrote in this transaction hold locks the second connection waits on.
	def test_a_key_committed_after_this_transaction_began_is_never_claimed_again(self):
		frappe.db.get_all("Doctype View", limit=1)
		mine = frappe.local.db
		frappe.connect(set_admin_as_user=False)
		theirs = frappe.local.db
		try:
			make_view(label="Race Probe", settings={}).insert()
			theirs.commit()
			frappe.local.db = mine
			try:
				claimed = KeySpace(DOCTYPE).claim("Race Probe")
			except frappe.QueryDeadlockError:
				claimed = None  # MariaDB 11.6+ refuses a locking read of a row changed since the snapshot.
			self.assertNotEqual(claimed, "race-probe")
		finally:
			frappe.local.db = theirs
			frappe.db.delete("Doctype View", {"reference_doctype": DOCTYPE, "label": "Race Probe"})
			theirs.commit()
			theirs.close()
			frappe.local.db = mine


class TestFind(DoctypeViewTestCase):
	def test_a_person_finds_their_own_view_and_the_site_s(self):
		make_view(label="Mine", user=self.person, settings={}).insert()
		make_view(label="Shared", settings={}).insert()

		with set_user(self.person):
			self.assertEqual(find(DOCTYPE, "mine"), {"key": "mine", "label": "Mine", "type": "List"})
			self.assertEqual(find(DOCTYPE, "shared")["label"], "Shared")

	def test_another_person_s_view_reads_as_missing_even_for_a_system_manager(self):
		make_view(label="Theirs", user=self.other, settings={}).insert()

		for user in (self.person, self.manager):
			with set_user(user):
				self.assertRaisesRegex(frappe.DoesNotExistError, "doesn't exist", find, DOCTYPE, "theirs")

	def test_a_missing_key_the_plain_view_and_an_unreadable_doctype_are_refused(self):
		make_view(settings={}).insert()

		with set_user(self.person):
			self.assertRaises(frappe.DoesNotExistError, find, DOCTYPE, "no-such-view")
			self.assertRaises(frappe.DoesNotExistError, find, DOCTYPE, "")
			self.assertRaises(frappe.PermissionError, find, PRIVATE_DOCTYPE, "anything")
