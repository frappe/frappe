# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.doctype.navigation_section.counts import cache_key
from frappe.desk.doctype.navigation_section.navigation_section import get_view_counts
from frappe.desk.doctype.navigation_section.scope import Scope
from frappe.desk.doctype.navigation_section.test_api import make_section, make_view
from frappe.desk.doctype.saved_view.test_api import make_user
from frappe.tests import IntegrationTestCase


def make_note(title, public=0):
	return frappe.get_doc(
		{"doctype": "Note", "title": title, "public": public}
	).insert(ignore_permissions=True)


class TestViewCounts(IntegrationTestCase):
	def setUp(self):
		self.member = make_user("saved-view-member@example.com", ["Desk User"])
		self.all = make_view("All")
		self.public_only = make_view("Public")
		self.public_only.filters = frappe.as_json([["public", "=", 1]])
		self.public_only.save(ignore_permissions=True)
		make_section("Views", [self.all, self.public_only])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.cache().delete_value(cache_key(Scope(reference_doctype="Note")))
		frappe.db.rollback()

	def test_each_view_counts_against_its_own_filters(self):
		make_note("public one", public=1)
		make_note("private one", public=0)

		counts = get_view_counts("Note")

		self.assertEqual(counts[str(self.public_only.name)], 1)
		self.assertGreaterEqual(counts[str(self.all.name)], 2)

	def test_counts_are_cached_within_the_window(self):
		make_note("first", public=1)
		before = get_view_counts("Note")[str(self.public_only.name)]

		make_note("second", public=1)
		cached = get_view_counts("Note")[str(self.public_only.name)]

		self.assertEqual(cached, before)

	def test_refresh_recounts_past_the_cache(self):
		"""The path a record create or delete takes: fresh counts within the window,
		not whatever the cache still holds."""
		make_note("first", public=1)
		get_view_counts("Note")

		make_note("second", public=1)

		self.assertEqual(get_view_counts("Note", refresh=True)[str(self.public_only.name)], 2)

	def test_a_cleared_cache_recomputes(self):
		make_note("first", public=1)
		get_view_counts("Note")

		make_note("second", public=1)
		frappe.cache().delete_value(cache_key(Scope(reference_doctype="Note")))

		self.assertEqual(get_view_counts("Note")[str(self.public_only.name)], 2)

	def test_counts_run_in_the_session_users_scope(self):
		"""A private note the manager owns is the manager's alone — the member's count
		of a view that isolates it is zero, because the count obeys their permissions."""
		make_note("secret-note-token", public=0)
		scoped = make_view("Scoped")
		scoped.filters = frappe.as_json([["title", "=", "secret-note-token"]])
		scoped.save(ignore_permissions=True)
		make_section("Scoped", [scoped])

		self.assertEqual(get_view_counts("Note")[str(scoped.name)], 1)

		frappe.set_user(self.member)
		frappe.cache().delete_value(cache_key(Scope(reference_doctype="Note")))
		self.assertEqual(get_view_counts("Note")[str(scoped.name)], 0)

	def test_a_view_counts_against_its_own_doctype_not_the_sidebars(self):
		"""A section may hold views of a doctype other than the one whose sidebar it is
		on — an app-level section is nothing but that. Counted against the sidebar's
		doctype instead, a filter on a field Note does not have comes back `None`."""
		for nth in ("first", "second"):
			frappe.get_doc({"doctype": "ToDo", "description": f"cross-doctype-count {nth}"}).insert(
				ignore_permissions=True
			)
		todos = frappe.get_doc(
			{
				"doctype": "Saved View",
				"label": "ToDos",
				"reference_doctype": "ToDo",
				"type": "list",
				"filters": frappe.as_json([["description", "like", "%cross-doctype-count%"]]),
			}
		).insert(ignore_permissions=True)
		make_section("Cross", [todos])

		self.assertEqual(get_view_counts("Note")[str(todos.name)], 2)

	def test_a_view_whose_filter_no_longer_applies_counts_as_none(self):
		broken = make_view("Broken")
		broken.filters = frappe.as_json([["no_such_field", "=", 1]])
		broken.save(ignore_permissions=True)
		make_section("Extra", [broken])

		self.assertIsNone(get_view_counts("Note")[str(broken.name)])
