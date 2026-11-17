# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.desk.doctype.doctype_view.api import (
	delete_view,
	find,
	publish_view,
	rename_view,
	save_view,
	save_view_as,
	view_settings,
)
from frappe.desk.doctype.doctype_view.doctype_view import SITE_ROW
from frappe.desk.doctype.doctype_view.test_app_views import AppViewCase, person_row, site_row
from frappe.desk.doctype.doctype_view.test_doctype_view import MANAGER, OTHER, PERSON, a_person
from frappe.desk.doctype.favourite.favourite import toggle_favourite
from frappe.exceptions import FrappeTypeError
from frappe.tests.classes.context_managers import set_user

DOCTYPE = "ToDo"
OPEN = {"filters": [["status", "=", "Open"]], "sort": [{"fieldname": "modified", "direction": "desc"}]}
CLOSED = {"filters": [["status", "=", "Closed"]]}


def stored_settings(name: str) -> dict:
	return frappe.parse_json(frappe.db.get_value("Doctype View", name, "settings"))


class SavedViewCase(AppViewCase):
	def setUp(self):
		super().setUp()
		frappe.db.delete("Doctype View", {"reference_doctype": DOCTYPE})
		frappe.db.delete("Favourite", {"reference_name": DOCTYPE})
		for user in (PERSON, OTHER):
			a_person(user)
		a_person(MANAGER, role="System Manager")
		self.folders.own_view("probe-open", label="Open probe", settings=OPEN)

	def row_at(self, key: str, user: str) -> str | None:
		return frappe.db.get_value("Doctype View", {"reference_doctype": DOCTYPE, "key": key, "user": user})


class TestSaving(SavedViewCase):
	def test_save_as_makes_an_own_view_with_a_key_from_its_label(self):
		with set_user(PERSON):
			view = save_view_as(DOCTYPE, " Mine Open ", OPEN)

		self.assertEqual(
			view, {"key": "mine-open", "label": "Mine Open", "type": "List", "layer": "own", "applies": True}
		)
		self.assertEqual(stored_settings(self.row_at("mine-open", PERSON)), OPEN)

	def test_save_as_takes_the_next_key_when_an_app_view_has_it(self):
		with set_user(PERSON):
			self.assertEqual(save_view_as(DOCTYPE, "Open probe", OPEN)["key"], "open-probe")
			self.assertEqual(save_view_as(DOCTYPE, "Probe Open", OPEN)["key"], "probe-open-2")

	def test_save_as_refuses_a_blank_label_and_a_stray_type(self):
		with set_user(PERSON):
			with self.assertRaisesRegex(frappe.ValidationError, "needs a name"):
				save_view_as(DOCTYPE, "  ", OPEN)
			with self.assertRaisesRegex(frappe.ValidationError, "not a view type"):
				save_view_as(DOCTYPE, "Mine", OPEN, type="Board")

	def test_a_person_saves_their_own_view(self):
		with set_user(PERSON):
			key = save_view_as(DOCTYPE, "Mine", OPEN)["key"]
			save_view(DOCTYPE, key, CLOSED)

		self.assertEqual(stored_settings(self.row_at(key, PERSON)), CLOSED)

	def test_a_save_must_hold_one_object(self):
		with set_user(PERSON):
			key = save_view_as(DOCTYPE, "Mine", OPEN)["key"]
			with self.assertRaises(FrappeTypeError):
				save_view(DOCTYPE, key, ["not", "an", "object"])

	def test_a_person_cannot_save_another_s_view_or_the_site_s(self):
		with set_user(OTHER):
			key = save_view_as(DOCTYPE, "Theirs", OPEN)["key"]
		site_key = site_row("site-probe", label="Site probe").key

		with set_user(PERSON):
			with self.assertRaises(frappe.DoesNotExistError):
				save_view(DOCTYPE, key, CLOSED)
			with self.assertRaises(frappe.PermissionError):
				save_view(DOCTYPE, site_key, CLOSED)
			with self.assertRaises(frappe.PermissionError):
				save_view(DOCTYPE, "probe-open", CLOSED)

		self.assertEqual(stored_settings(self.row_at(key, OTHER)), OPEN)

	def test_a_site_administrator_saves_a_site_view(self):
		site_row("site-probe", label="Site probe")
		with set_user(MANAGER):
			save_view(DOCTYPE, "site-probe", CLOSED)

		self.assertEqual(stored_settings(self.row_at("site-probe", SITE_ROW)), CLOSED)

	def test_an_administrator_saves_an_app_view_as_a_site_row_that_overrides_it(self):
		with set_user(MANAGER):
			view = save_view(DOCTYPE, "probe-open", CLOSED)
			self.assertEqual(
				view,
				{
					"key": "probe-open",
					"label": "Open probe",
					"type": "List",
					"layer": "site",
					"applies": True,
				},
			)
			self.assertEqual(stored_settings(self.row_at("probe-open", SITE_ROW)), CLOSED)
			save_view(DOCTYPE, "probe-open", OPEN)  # a second save edits the same row

		self.assertEqual(
			frappe.db.count("Doctype View", {"reference_doctype": DOCTYPE, "key": "probe-open"}), 1
		)
		with set_user(PERSON):
			self.assertEqual(view_settings(DOCTYPE, "probe-open")["layer"], "site")

	def test_an_override_keeps_the_files_label_not_the_savers_translation(self):
		translate = lambda text: f"fr {text}"  # noqa: E731
		with set_user(MANAGER), patch("frappe.desk.doctype.doctype_view.key_space._", translate):
			save_view(DOCTYPE, "probe-open", CLOSED)

		label = frappe.db.get_value("Doctype View", self.row_at("probe-open", SITE_ROW), "label")
		self.assertEqual(label, "Open probe")

	def test_the_plain_view_and_a_missing_view_are_not_saved_here(self):
		with set_user(MANAGER):
			for key in ("list", "no-such-view"):
				with self.assertRaises(frappe.DoesNotExistError):
					save_view(DOCTYPE, key, CLOSED)


class TestRenaming(SavedViewCase):
	def test_a_rename_changes_the_label_and_keeps_the_key(self):
		with set_user(PERSON):
			key = save_view_as(DOCTYPE, "Mine", OPEN)["key"]
			view = rename_view(DOCTYPE, key, "Renamed")

		self.assertEqual((view["key"], view["label"]), (key, "Renamed"))
		self.assertEqual(frappe.db.get_value("Doctype View", self.row_at(key, PERSON), "key"), key)

	def test_a_rename_needs_a_name(self):
		with set_user(PERSON):
			key = save_view_as(DOCTYPE, "Mine", OPEN)["key"]
			with self.assertRaisesRegex(frappe.ValidationError, "needs a name"):
				rename_view(DOCTYPE, key, " ")

	def test_only_an_administrator_renames_a_site_view_and_nobody_an_app_view(self):
		site_row("site-probe", label="Site probe")
		with set_user(PERSON), self.assertRaises(frappe.PermissionError):
			rename_view(DOCTYPE, "site-probe", "Mine now")

		with set_user(MANAGER):
			self.assertEqual(rename_view(DOCTYPE, "site-probe", "Shared")["label"], "Shared")
			with self.assertRaisesRegex(frappe.ValidationError, "renamed in its file"):
				rename_view(DOCTYPE, "probe-open", "Mine now")


class TestDeleting(SavedViewCase):
	def test_a_delete_removes_the_row_with_its_stars_and_defaults(self):
		with set_user(PERSON):
			key = save_view_as(DOCTYPE, "Mine", OPEN)["key"]
			toggle_favourite("DocType", DOCTYPE, add=True, view=key)
			frappe.get_doc(
				{"doctype": "Default View", "reference_doctype": DOCTYPE, "user": PERSON, "view": key}
			).insert(ignore_permissions=True)

			self.assertEqual(delete_view(DOCTYPE, key), {"key": key, "restored": False, "default_view": None})

		self.assertIsNone(self.row_at(key, PERSON))
		self.assertFalse(frappe.db.exists("Favourite", {"reference_name": DOCTYPE, "view": key}))
		self.assertFalse(frappe.db.exists("Default View", {"reference_doctype": DOCTYPE, "view": key}))

	def test_a_delete_answers_the_default_the_layers_left_resolve_to(self):
		frappe.get_doc(
			{"doctype": "Default View", "reference_doctype": DOCTYPE, "user": SITE_ROW, "view": "probe-open"}
		).insert(ignore_permissions=True)
		with set_user(PERSON):
			key = save_view_as(DOCTYPE, "Mine", OPEN)["key"]
			frappe.get_doc(
				{"doctype": "Default View", "reference_doctype": DOCTYPE, "user": PERSON, "view": key}
			).insert(ignore_permissions=True)

			self.assertEqual(delete_view(DOCTYPE, key)["default_view"], "probe-open")

	def test_a_person_cannot_delete_another_s_view_or_the_site_s(self):
		with set_user(OTHER):
			key = save_view_as(DOCTYPE, "Theirs", OPEN)["key"]
		site_row("site-probe", label="Site probe")

		with set_user(PERSON):
			with self.assertRaises(frappe.DoesNotExistError):
				delete_view(DOCTYPE, key)
			with self.assertRaises(frappe.PermissionError):
				delete_view(DOCTYPE, "site-probe")

		self.assertTrue(self.row_at(key, OTHER))
		self.assertTrue(self.row_at("site-probe", SITE_ROW))

	def test_deleting_a_site_override_restores_the_app_view_and_keeps_its_stars(self):
		with set_user(MANAGER):
			save_view(DOCTYPE, "probe-open", CLOSED)
			toggle_favourite("DocType", DOCTYPE, add=True, view="probe-open")

			self.assertEqual(
				delete_view(DOCTYPE, "probe-open"),
				{"key": "probe-open", "restored": True, "default_view": None},
			)

			self.assertEqual(find(DOCTYPE, "probe-open")["layer"], "app")
			self.assertEqual(view_settings(DOCTYPE, "probe-open")["settings"], OPEN)
		self.assertTrue(frappe.db.exists("Favourite", {"reference_name": DOCTYPE, "view": "probe-open"}))

	def test_an_app_view_cannot_be_deleted(self):
		for user in (PERSON, MANAGER):
			with set_user(user), self.assertRaisesRegex(frappe.ValidationError, "removing its file"):
				delete_view(DOCTYPE, "probe-open")


class TestPublishing(SavedViewCase):
	def test_an_administrator_publishes_their_view_under_the_same_key(self):
		with set_user(MANAGER):
			key = save_view_as(DOCTYPE, "Mine", OPEN)["key"]
			toggle_favourite("DocType", DOCTYPE, add=True, view=key)

			self.assertEqual(publish_view(DOCTYPE, key)["layer"], "site")

		self.assertIsNone(self.row_at(key, MANAGER))
		self.assertEqual(stored_settings(self.row_at(key, SITE_ROW)), OPEN)
		self.assertTrue(
			frappe.db.exists("Favourite", {"user": MANAGER, "reference_name": DOCTYPE, "view": key})
		)
		with set_user(PERSON):
			self.assertEqual(find(DOCTYPE, key)["layer"], "site")

	def test_a_person_who_is_not_an_administrator_cannot_publish(self):
		with set_user(PERSON):
			key = save_view_as(DOCTYPE, "Mine", OPEN)["key"]
			with self.assertRaises(frappe.PermissionError):
				publish_view(DOCTYPE, key)

		self.assertTrue(self.row_at(key, PERSON))
		self.assertIsNone(self.row_at(key, SITE_ROW))

	def test_only_an_own_view_is_published(self):
		site_row("site-probe", label="Site probe")
		with set_user(OTHER):
			theirs = save_view_as(DOCTYPE, "Theirs", OPEN)["key"]

		with set_user(MANAGER):
			with self.assertRaisesRegex(frappe.ValidationError, "own views"):
				publish_view(DOCTYPE, "site-probe")
			with self.assertRaisesRegex(frappe.ValidationError, "own views"):
				publish_view(DOCTYPE, "probe-open")
			with self.assertRaises(frappe.DoesNotExistError):
				publish_view(DOCTYPE, theirs)

	def test_a_view_at_an_app_key_cannot_move_to_the_site(self):
		person_row("Late Probe")  # made before the app shipped the same key
		self.folders.own_view("late-probe")
		with set_user("Administrator"), self.assertRaisesRegex(frappe.ValidationError, "address of an app"):
			publish_view(DOCTYPE, "late-probe")


class TestReadingSettings(SavedViewCase):
	def test_each_layer_answers_with_its_settings_and_whether_the_caller_saves_it(self):
		site_row("site-probe", label="Site probe")
		with set_user(PERSON):
			own = save_view_as(DOCTYPE, "Mine", OPEN)["key"]
			read = lambda key: view_settings(DOCTYPE, key)  # noqa: E731

			self.assertEqual(
				(read(own)["layer"], read(own)["settings"], read(own)["saveable"]), ("own", OPEN, True)
			)
			self.assertEqual((read("probe-open")["layer"], read("probe-open")["settings"]), ("app", OPEN))
			self.assertFalse(read("probe-open")["saveable"])
			self.assertEqual((read("site-probe")["layer"], read("site-probe")["saveable"]), ("site", False))

		with set_user(MANAGER):
			self.assertTrue(view_settings(DOCTYPE, "probe-open")["saveable"])

	def test_the_plain_view_answers_with_its_layers_merged(self):
		with set_user(PERSON):
			reply = view_settings(DOCTYPE, "list")

		self.assertEqual((reply["layer"], reply["type"], reply["saveable"]), (None, "List", True))

	def test_another_person_s_view_reads_as_missing(self):
		with set_user(OTHER):
			key = save_view_as(DOCTYPE, "Theirs", OPEN)["key"]

		with set_user(PERSON), self.assertRaises(frappe.DoesNotExistError):
			view_settings(DOCTYPE, key)
