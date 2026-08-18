# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.doctype.navigation_section.navigation_section import get_sidebar
from frappe.desk.doctype.navigation_section.scope import DEFAULT_APP
from frappe.desk.doctype.saved_view.api import (
	add_to_sidebar,
	create_view,
	delete_view,
	duplicate_view,
	get_landing_view,
	get_pool,
	move_view,
	remove_from_sidebar,
	save_landing_state,
	save_view_state,
	set_as_default,
)
from frappe.tests import IntegrationTestCase


def make_user(email, roles):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": email.split("@")[0], "roles": []}
		).insert(ignore_permissions=True)

	user = frappe.get_doc("User", email)
	user.set("roles", [])
	for role in roles:
		user.append("roles", {"role": role})
	user.save(ignore_permissions=True)
	return email


def sections(reference_doctype="Note", app=DEFAULT_APP):
	return {
		section["label"]: section["items"] for section in get_sidebar(reference_doctype, app=app)["sections"]
	}


def labels(reference_doctype="Note", app=DEFAULT_APP):
	return {
		label: [view["label"] for view in views] for label, views in sections(reference_doctype, app).items()
	}


class TestSavedViewApi(IntegrationTestCase):
	def setUp(self):
		self.member = make_user("saved-view-member@example.com", ["Desk User"])
		self.other = make_user("saved-view-other@example.com", ["Desk User"])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_a_new_personal_view_lands_in_the_personal_section(self):
		frappe.set_user(self.member)

		create_view("Note", "Mine")

		self.assertEqual(labels()["Personal"], ["Mine"])

	def test_a_manager_can_create_a_shared_view(self):
		create_view("Note", "Everyones", shared=True)

		self.assertEqual(labels()["Views"], ["Everyones"])

	def test_a_shared_view_lands_in_views_not_in_another_shared_section(self):
		"""CRM seeds a "Pipeline" section alongside "Views"; a new shared view is not
		its business, however the two are ordered."""
		frappe.get_doc(
			{
				"doctype": "Navigation Section",
				"label": "Pipeline",
				"app": DEFAULT_APP,
				"reference_doctype": "Note",
			}
		).insert()

		create_view("Note", "Everyones", shared=True)

		self.assertEqual(labels()["Pipeline"], [])
		self.assertEqual(labels()["Views"], ["Everyones"])

	def test_a_named_section_takes_the_view_instead_of_the_visibility_default(self):
		"""What the editor's per-section + asks for. Named on the way in rather than
		moved afterwards: the default placement would create a "Views" of its own
		first, and a move would then leave it behind empty."""
		pipeline = frappe.get_doc(
			{
				"doctype": "Navigation Section",
				"label": "Pipeline",
				"app": DEFAULT_APP,
				"reference_doctype": "Note",
			}
		).insert()

		create_view("Note", "Everyones", shared=True, section=pipeline.name)

		placed = labels()
		self.assertEqual(placed["Pipeline"], ["Everyones"])
		self.assertNotIn("Views", placed)

	def test_a_section_the_caller_cannot_write_falls_back_to_the_default(self):
		"""A member pressing + on a shared section is asking for a personal view, which
		cannot sit where everyone reads it. Where they may put one is what the default
		placement answers, so it answers rather than the create failing."""
		frappe.get_doc(
			{
				"doctype": "Navigation Section",
				"label": "Views",
				"app": DEFAULT_APP,
				"reference_doctype": "Note",
			}
		).insert()
		shared = frappe.get_value("Navigation Section", {"label": "Views", "user": ("in", ("", None))})
		frappe.set_user(self.member)

		create_view("Note", "Mine", section=shared)

		placed = labels()
		self.assertEqual(placed["Personal"], ["Mine"])
		self.assertEqual(placed["Views"], [])

	def test_a_section_from_another_sidebar_is_refused(self):
		"""The name comes off the client, so it is checked against the scope the view is
		being created in rather than taken on trust."""
		theirs = frappe.get_doc(
			{
				"doctype": "Navigation Section",
				"label": "Views",
				"app": "helpdesk",
				"reference_doctype": "Note",
			}
		).insert()

		with self.assertRaises(frappe.ValidationError):
			create_view("Note", "Mine", section=theirs.name)

	def test_a_view_created_for_another_app_lands_in_that_apps_section(self):
		"""A view is app-agnostic; the section it is placed in is not."""
		create_view("Note", "Ours", shared=True)

		create_view("Note", "Theirs", shared=True, app="helpdesk")

		self.assertEqual(labels()["Views"], ["Ours"])
		self.assertEqual(labels(app="helpdesk")["Views"], ["Theirs"])

	def test_a_view_placed_only_in_another_app_counts_as_unplaced_here(self):
		"""Placement is per app, so this app's + menu still offers it."""
		view = create_view("Note", "Theirs", shared=True, app="helpdesk")

		self.assertIn(str(view), [str(entry["name"]) for entry in get_pool("Note")])

	def test_a_member_cannot_create_a_shared_view(self):
		frappe.set_user(self.member)

		with self.assertRaises(frappe.PermissionError):
			create_view("Note", "Everyones", shared=True)

	def test_a_member_cannot_edit_a_shared_view(self):
		view = create_view("Note", "Everyones", shared=True)
		frappe.set_user(self.member)

		saved_view = frappe.get_doc("Saved View", view)
		saved_view.label = "Renamed"
		with self.assertRaises(frappe.PermissionError):
			saved_view.save()

	def test_a_member_cannot_delete_a_shared_view(self):
		view = create_view("Note", "Everyones", shared=True)
		frappe.set_user(self.member)

		with self.assertRaises(frappe.PermissionError):
			delete_view(view)

	def test_a_member_cannot_claim_a_shared_view_by_moving_it_to_personal(self):
		view = create_view("Note", "Everyones", shared=True)
		frappe.set_user(self.member)

		with self.assertRaises(frappe.PermissionError):
			move_view(view, shared=False)

	def test_a_member_owns_their_personal_view(self):
		frappe.set_user(self.member)
		view = create_view("Note", "Mine")

		saved_view = frappe.get_doc("Saved View", view)
		saved_view.label = "Renamed"
		saved_view.save()

		self.assertEqual(labels()["Personal"], ["Renamed"])

	def test_a_member_cannot_touch_another_members_view(self):
		frappe.set_user(self.other)
		view = create_view("Note", "Theirs")

		frappe.set_user(self.member)
		with self.assertRaises(frappe.PermissionError):
			delete_view(view)

	def test_another_members_view_stays_out_of_the_sidebar(self):
		frappe.set_user(self.other)
		create_view("Note", "Theirs")

		frappe.set_user(self.member)
		self.assertEqual(labels().get("Personal"), None)

	def test_removing_from_the_sidebar_keeps_the_record(self):
		frappe.set_user(self.member)
		view = create_view("Note", "Mine")

		remove_from_sidebar(view)

		self.assertTrue(frappe.db.exists("Saved View", view))
		self.assertEqual(labels()["Personal"], [])

	def test_a_removed_view_shows_up_in_the_pool(self):
		frappe.set_user(self.member)
		view = create_view("Note", "Mine")
		remove_from_sidebar(view)

		self.assertEqual([entry["label"] for entry in get_pool("Note")], ["Mine"])

	def test_a_placed_view_is_not_in_the_pool(self):
		frappe.set_user(self.member)
		create_view("Note", "Mine")

		self.assertEqual(get_pool("Note"), [])

	def test_adding_a_pool_view_back_places_it_again(self):
		frappe.set_user(self.member)
		view = create_view("Note", "Mine")
		remove_from_sidebar(view)

		add_to_sidebar(view)

		self.assertEqual(labels()["Personal"], ["Mine"])

	def test_deleting_removes_the_record_and_its_placement(self):
		frappe.set_user(self.member)
		view = create_view("Note", "Mine")

		delete_view(view)

		self.assertFalse(frappe.db.exists("Saved View", view))
		self.assertEqual(labels()["Personal"], [])

	def test_deleting_clears_a_placement_the_deleter_cannot_otherwise_write(self):
		frappe.set_user(self.member)
		view = create_view("Note", "Mine")

		frappe.set_user("Administrator")
		delete_view(view)

		frappe.set_user(self.member)
		self.assertEqual(labels()["Personal"], [])

	def test_an_unplaced_shared_view_is_offered_to_managers_only(self):
		view = create_view("Note", "Everyones", shared=True)
		remove_from_sidebar(view)

		self.assertEqual([entry["label"] for entry in get_pool("Note")], ["Everyones"])

		frappe.set_user(self.member)
		self.assertEqual(get_pool("Note"), [])

	def test_duplicating_a_shared_view_gives_the_member_a_personal_copy(self):
		view = frappe.get_doc(
			{
				"doctype": "Saved View",
				"label": "Open",
				"reference_doctype": "Note",
				"type": "list",
				"order_by": "modified desc",
			}
		).insert()
		frappe.set_user(self.member)

		copy = duplicate_view(view.name)

		self.assertEqual(labels()["Personal"], ["Open (copy)"])
		self.assertEqual(frappe.db.get_value("Saved View", copy, "order_by"), "modified desc")
		self.assertEqual(frappe.db.get_value("Saved View", copy, "user"), self.member)

	def test_moving_a_view_to_shared_flips_its_visibility(self):
		view = create_view("Note", "Mine")

		move_view(view, shared=True)

		self.assertEqual(frappe.db.get_value("Saved View", view, "user"), "")
		self.assertEqual(labels()["Views"], ["Mine"])
		self.assertEqual(labels()["Personal"], [])

	def test_moving_a_view_to_personal_flips_it_back(self):
		view = create_view("Note", "Everyones", shared=True)

		move_view(view, shared=False)

		self.assertEqual(frappe.db.get_value("Saved View", view, "user"), "Administrator")
		self.assertEqual(labels()["Views"], [])

	def test_set_as_default_copies_the_payload_into_the_users_default_record(self):
		view = create_view("Note", "Everyones", shared=True)
		frappe.set_value("Saved View", view, "order_by", "creation asc")
		frappe.set_user(self.member)

		default = set_as_default(view)

		record = frappe.get_doc("Saved View", default)
		self.assertEqual(record.user, self.member)
		self.assertEqual(record.is_default, 1)
		self.assertEqual(record.order_by, "creation asc")
		self.assertEqual(str(record.source_view), str(view))

	def test_set_as_default_reuses_the_one_default_record(self):
		frappe.set_user(self.member)
		first = create_view("Note", "First")
		second = create_view("Note", "Second")

		self.assertEqual(set_as_default(first), set_as_default(second))

	def test_the_default_record_is_neither_on_the_sidebar_nor_in_the_pool(self):
		frappe.set_user(self.member)
		view = create_view("Note", "Mine")
		set_as_default(view)

		self.assertEqual(labels()["Personal"], ["Mine"])
		self.assertEqual(get_pool("Note"), [])

	def test_the_default_view_falls_back_to_the_first_shared_view(self):
		first = create_view("Note", "All", shared=True)
		create_view("Note", "Open", shared=True)
		frappe.set_user(self.member)

		self.assertEqual(str(get_sidebar("Note")["default_view"]), str(first))

	def test_setting_a_default_points_the_sidebar_at_its_source_view(self):
		shared = create_view("Note", "All", shared=True)
		frappe.set_user(self.member)
		mine = create_view("Note", "Mine")
		set_as_default(mine)

		self.assertEqual(str(get_sidebar("Note")["default_view"]), str(mine))

		set_as_default(shared)
		self.assertEqual(str(get_sidebar("Note")["default_view"]), str(shared))

	def test_tweaking_the_landing_leaves_the_default_view_marked(self):
		create_view("Note", "All", shared=True)
		frappe.set_user(self.member)
		mine = create_view("Note", "Mine")
		set_as_default(mine)

		save_landing_state("Note", order_by="creation asc")

		self.assertEqual(str(get_sidebar("Note")["default_view"]), str(mine))

	def test_the_default_view_is_absent_when_no_view_can_stand_in(self):
		frappe.set_user(self.member)
		self.assertIsNone(get_sidebar("Note")["default_view"])

	def test_the_sidebar_reports_whether_the_caller_manages_the_shared_area(self):
		self.assertTrue(get_sidebar("Note")["can_manage_shared"])

		frappe.set_user(self.member)
		self.assertFalse(get_sidebar("Note")["can_manage_shared"])

	def test_saving_state_writes_the_live_list_into_a_personal_view(self):
		frappe.set_user(self.member)
		view = create_view("Note", "Mine")

		save_view_state(view, order_by="creation asc", filters='[["status", "=", "Open"]]')

		self.assertEqual(frappe.db.get_value("Saved View", view, "order_by"), "creation asc")
		self.assertEqual(frappe.db.get_value("Saved View", view, "filters"), '[["status", "=", "Open"]]')

	def test_saving_state_clears_a_field_the_tweak_dropped(self):
		frappe.set_user(self.member)
		view = create_view("Note", "Mine", order_by="creation asc")

		save_view_state(view, order_by=None)

		self.assertFalse(frappe.db.get_value("Saved View", view, "order_by"))

	def test_a_member_cannot_save_state_into_a_shared_view(self):
		view = create_view("Note", "Everyones", shared=True)
		frappe.set_user(self.member)

		with self.assertRaises(frappe.PermissionError):
			save_view_state(view, order_by="creation asc")

	def test_a_manager_can_save_state_into_a_shared_view(self):
		view = create_view("Note", "Everyones", shared=True)

		save_view_state(view, order_by="creation asc")

		self.assertEqual(frappe.db.get_value("Saved View", view, "order_by"), "creation asc")

	def test_save_as_new_seeds_a_placed_personal_view_from_the_live_state(self):
		frappe.set_user(self.member)

		view = create_view("Note", "From tweak", order_by="creation asc")

		self.assertEqual(labels()["Personal"], ["From tweak"])
		self.assertEqual(frappe.db.get_value("Saved View", view, "order_by"), "creation asc")
		self.assertEqual(frappe.db.get_value("Saved View", view, "user"), self.member)

	def test_the_landing_view_is_absent_until_a_tweak_is_auto_saved(self):
		frappe.set_user(self.member)

		self.assertIsNone(get_landing_view("Note"))

	def test_auto_saving_the_landing_state_creates_a_personal_default(self):
		frappe.set_user(self.member)

		save_landing_state("Note", order_by="creation asc")

		landing = get_landing_view("Note")
		self.assertEqual(landing["order_by"], "creation asc")
		record = frappe.get_doc("Saved View", landing["name"])
		self.assertEqual(record.user, self.member)
		self.assertEqual(record.is_default, 1)

	def test_auto_saving_the_landing_state_reuses_the_one_default(self):
		frappe.set_user(self.member)

		first = save_landing_state("Note", order_by="creation asc")
		second = save_landing_state("Note", order_by="modified desc")

		self.assertEqual(first, second)
		self.assertEqual(get_landing_view("Note")["order_by"], "modified desc")

	def test_the_landing_default_is_neither_on_the_sidebar_nor_in_the_pool(self):
		frappe.set_user(self.member)

		save_landing_state("Note", order_by="creation asc")

		self.assertEqual(labels().get("Personal"), None)
		self.assertEqual(get_pool("Note"), [])

	def test_each_user_lands_on_their_own_default(self):
		frappe.set_user(self.member)
		save_landing_state("Note", order_by="creation asc")

		frappe.set_user(self.other)
		self.assertIsNone(get_landing_view("Note"))
