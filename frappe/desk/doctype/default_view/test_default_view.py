# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.doctype.default_view.api import clear, save
from frappe.desk.doctype.default_view.resolver import DefaultViews
from frappe.desk.doctype.doctype_view.test_doctype_view import (
	DOCTYPE,
	MANAGER,
	OTHER,
	PERSON,
	PRIVATE_DOCTYPE,
	a_person,
	make_view,
)
from frappe.shell.boot import get_boot
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user


def make_default(**kwargs):
	return frappe.get_doc({"doctype": "Default View", "reference_doctype": DOCTYPE, **kwargs})


def default_of(user: str, doctype: str = DOCTYPE) -> str | None:
	return DefaultViews(user).addresses([doctype]).get(doctype)


class DefaultViewTestCase(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		# The class rolls back once, so each test starts from no rows of its own.
		for doctype in ("Default View", "Doctype View"):
			frappe.db.delete(doctype, {"reference_doctype": ("in", (DOCTYPE, PRIVATE_DOCTYPE))})
		self.person = a_person(PERSON)
		self.other = a_person(OTHER)
		self.manager = a_person(MANAGER, role="System Manager")
		self.site_row = make_view(label="Open Notes", settings={}).insert()
		self.own_row = make_view(label="My Notes", user=self.person, settings={}).insert()
		self.site_view, self.own_view = self.site_row.key, self.own_row.key


class TestDefaultView(DefaultViewTestCase):
	def test_a_pointer_to_a_saved_view_keeps_no_type(self):
		doc = make_default(view=self.site_view, type="List").insert()

		self.assertEqual(frappe.db.get_value("Default View", doc.name, ["user", "type"]), ("", None))

	def test_a_plain_view_pointer_needs_a_known_type(self):
		self.assertRaisesRegex(frappe.ValidationError, "not a view type", make_default(type="Board").insert)

	def test_a_second_default_at_one_layer_is_refused_cleanly(self):
		make_default(type="List").insert()

		self.assertRaisesRegex(
			frappe.ValidationError, "already has a default view", make_default(view=self.site_view).insert
		)

	def test_the_unique_index_holds_one_default_per_doctype_per_layer(self):
		make_default(user=self.person, type="List").insert()
		table = frappe.qb.DocType("Default View")
		twin = (
			frappe.qb.into(table)
			.columns("name", "reference_doctype", "user", "view", "type")
			.insert(frappe.generate_hash(), DOCTYPE, self.person, self.own_view, None)
		)

		frappe.db.savepoint("twin")
		with self.assertRaises(Exception) as refusal:
			twin.run()
		frappe.db.rollback(save_point="twin")

		self.assertTrue(frappe.db.is_unique_key_violation(refusal.exception))

	def test_a_person_reads_the_site_row_and_their_own_and_only_a_system_manager_writes_the_site_s(self):
		site = make_default(type="List").insert()
		own = make_default(user=self.person, type="List").insert()
		other = make_default(user=self.other, type="List").insert()

		self.assertTrue(frappe.has_permission("Default View", "read", site, user=self.person))
		self.assertTrue(frappe.has_permission("Default View", "read", own, user=self.person))
		self.assertFalse(frappe.has_permission("Default View", "read", other, user=self.person))
		self.assertFalse(frappe.has_permission("Default View", "write", site, user=self.person))
		self.assertTrue(frappe.has_permission("Default View", "write", site, user=self.manager))
		with set_user(self.person):
			self.assertEqual(
				set(frappe.get_list("Default View", pluck="name")) & {site.name, own.name, other.name},
				{site.name, own.name},
			)

	def test_deleting_a_person_s_own_view_deletes_their_pointer_to_it_and_no_other(self):
		make_default(user=self.person, view=self.own_view).insert()
		make_default(view=self.site_view).insert()

		self.own_row.delete()
		self.site_row.delete()

		self.assertFalse(frappe.db.exists("Default View", {"user": self.person}))
		self.assertTrue(frappe.db.exists("Default View", {"reference_doctype": DOCTYPE, "user": ""}))


class TestResolver(DefaultViewTestCase):
	def test_no_pointer_at_any_layer_gives_no_default(self):
		self.assertIsNone(default_of(self.person))
		self.assertNotIn(DOCTYPE, DefaultViews(self.person).addresses())

	def test_a_person_s_own_default_wins_over_the_site_s(self):
		make_default(view=self.site_view).insert()
		make_default(user=self.person, view=self.own_view).insert()

		self.assertEqual(default_of(self.person), self.own_view)
		self.assertEqual(default_of(self.other), self.site_view)

	def test_a_plain_view_default_is_its_type_s_address(self):
		make_default(view=self.site_view).insert()
		make_default(user=self.person, type="List").insert()

		self.assertEqual(default_of(self.person), "list")

	def test_a_deleted_view_falls_through_to_the_site_s_default(self):
		make_default(view=self.site_view).insert()
		make_default(user=self.person, view="gone").insert()

		self.assertEqual(default_of(self.person), self.site_view)

	def test_a_dangling_site_default_falls_through_to_no_default(self):
		make_default(view=self.site_view).insert()
		self.site_row.delete()

		self.assertIsNone(default_of(self.person))

	def test_another_person_s_private_view_is_passed_over(self):
		make_default(view=self.own_view).insert()

		self.assertEqual(default_of(self.person), self.own_view)
		self.assertIsNone(default_of(self.other))

	def test_a_doctype_the_person_cannot_read_has_no_default(self):
		make_default(reference_doctype=PRIVATE_DOCTYPE, type="List").insert()

		self.assertIsNone(default_of(self.person, PRIVATE_DOCTYPE))
		self.assertEqual(default_of(self.manager, PRIVATE_DOCTYPE), "list")

	def test_a_pointer_at_a_deleted_doctype_is_passed_over(self):
		make_default(view=self.site_view).insert()
		table = frappe.qb.DocType("Default View")
		frappe.qb.into(table).columns("name", "reference_doctype", "user", "view", "type").insert(
			frappe.generate_hash(), "A Deleted Doctype", "", "", "List"
		).run()

		self.assertEqual(DefaultViews(self.person).addresses(), {DOCTYPE: self.site_view})

	def test_boot_carries_each_resolved_default(self):
		make_default(view=self.site_view).insert()

		with set_user(self.person):
			boot = get_boot("/apps/desk")

		self.assertEqual(boot["default_views"].get(DOCTYPE), self.site_view)


class TestApi(DefaultViewTestCase):
	def test_a_person_sets_and_clears_their_own_default(self):
		with set_user(self.person):
			self.assertEqual(save(DOCTYPE, self.own_view, "user"), self.own_view)
			self.assertEqual(save(DOCTYPE, "list", "user"), "list")
			self.assertIsNone(clear(DOCTYPE, "user"))

		self.assertFalse(frappe.db.exists("Default View", {"user": self.person}))

	def test_clearing_one_s_own_default_falls_back_to_the_site_s(self):
		make_default(view=self.site_view).insert()

		with set_user(self.person):
			save(DOCTYPE, self.own_view, "user")
			self.assertEqual(clear(DOCTYPE, "user"), self.site_view)

	def test_the_site_layer_needs_a_system_manager(self):
		with set_user(self.person):
			self.assertRaises(frappe.PermissionError, save, DOCTYPE, self.site_view, "site")
			self.assertRaises(frappe.PermissionError, clear, DOCTYPE, "site")

		with set_user(self.manager):
			save(DOCTYPE, self.site_view, "site")

		self.assertEqual(default_of(self.other), self.site_view)

	def test_a_key_that_names_no_view_this_layer_may_point_at_is_refused(self):
		with set_user(self.person):
			self.assertRaises(frappe.DoesNotExistError, save, DOCTYPE, "gone", "user")

		with set_user(self.other):
			self.assertRaises(frappe.DoesNotExistError, save, DOCTYPE, self.own_view, "user")

		with set_user(self.manager):
			self.assertRaises(frappe.DoesNotExistError, save, DOCTYPE, self.own_view, "site")

	def test_a_second_save_moves_the_one_pointer(self):
		with set_user(self.person):
			save(DOCTYPE, self.own_view, "user")
			save(DOCTYPE, self.site_view, "user")

		self.assertEqual(frappe.db.count("Default View", {"user": self.person}), 1)
		self.assertEqual(default_of(self.person), self.site_view)

	def test_a_doctype_the_caller_cannot_read_is_refused(self):
		with set_user(self.person):
			self.assertRaises(frappe.PermissionError, save, PRIVATE_DOCTYPE, "list", "user")
