# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.doctype.doctype_view.api import get, reset, save
from frappe.exceptions import FrappeTypeError
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user

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
			self.assertEqual(get(DOCTYPE), {"site": None, "user": None})

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

	def test_a_save_takes_the_patch_as_a_json_string_too(self):
		with set_user(self.person):
			rows = save(DOCTYPE, "List", "user", '{"quick_filter_fields": ["title"]}')

		self.assertEqual(rows["user"], {"quick_filter_fields": ["title"]})

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
			self.assertEqual(get(DOCTYPE), {"site": {"sort": []}, "user": {"columns": []}})

		with set_user(self.other):
			self.assertEqual(get(DOCTYPE), {"site": {"sort": []}, "user": None})

	def test_a_doctype_the_caller_cannot_read_is_refused(self):
		with set_user(self.person):
			self.assertRaises(frappe.PermissionError, get, PRIVATE_DOCTYPE)

	def test_a_bad_argument_is_refused_before_anything_is_read(self):
		with set_user(self.person):
			self.assertRaises(frappe.ValidationError, get, "No Such Doctype")
			self.assertRaises(frappe.ValidationError, get, DOCTYPE, "Kanban")
			self.assertRaises(frappe.ValidationError, save, DOCTYPE, "List", "everyone", {})
			self.assertRaises(frappe.ValidationError, save, DOCTYPE, "List", "user", "not json")
			self.assertRaises(FrappeTypeError, save, DOCTYPE, "List", "user", ["a list"])
			self.assertRaises(FrappeTypeError, reset, DOCTYPE, "List", "user", ["a list"])
