# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.doctype.saved_view.api import move_view
from frappe.desk.doctype.saved_view.permissions import can_manage_shared
from frappe.desk.doctype.saved_view.test_api import make_user
from frappe.tests import IntegrationTestCase


def make_view(**kwargs):
	values = {
		"doctype": "Saved View",
		"label": "Open Notes",
		"reference_doctype": "Note",
		"type": "list",
	}
	values.update(kwargs)
	return frappe.get_doc(values)


class TestSavedView(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_shared_view_has_no_user(self):
		view = make_view().insert()
		self.assertEqual(view.user, None)
		self.assertEqual(view.type, "list")

	def test_default_view_must_belong_to_a_user(self):
		with self.assertRaises(frappe.ValidationError):
			make_view(is_default=1).insert()

	def test_per_user_default_is_allowed(self):
		view = make_view(is_default=1, user="Administrator").insert()
		self.assertEqual(view.user, "Administrator")

	def test_carries_kanban_and_group_by_configuration(self):
		view = make_view(
			type="kanban",
			column_field="status",
			title_field="title",
			group_by_field="owner",
			kanban_columns='[{"name": "Open"}]',
			kanban_fields='["title"]',
		).insert()

		view.reload()
		self.assertEqual(view.type, "kanban")
		self.assertEqual(view.column_field, "status")
		self.assertEqual(view.group_by_field, "owner")
		self.assertEqual(frappe.parse_json(view.kanban_fields), ["title"])


class TestPersonalRecordOwnership(IntegrationTestCase):
	"""`if_owner` asks about `owner` while these DocTypes scope on `user`, so a personal
	record is owned by its user -- including one seeded or migrated for them."""

	def setUp(self):
		self.member = make_user("saved-view-owner@example.com", ["Desk User"])
		self.manager = make_user("saved-view-mover@example.com", ["Desk User", "System Manager"])

	def tearDown(self):
		frappe.flags.in_migrate = False
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_a_view_made_for_someone_is_owned_by_them(self):
		view = make_view(user=self.member).insert(ignore_permissions=True)

		self.assertEqual(view.owner, self.member)

	def test_a_view_migrated_for_someone_is_owned_by_them(self):
		"""Under in_install/in_patch/in_migrate `creation` goes unstamped, which `db_insert`
		reads as licence to re-stamp `owner` from the session."""
		frappe.flags.in_migrate = True
		view = make_view(user=self.member).insert(ignore_permissions=True)

		self.assertEqual(frappe.db.get_value("Saved View", view.name, "owner"), self.member)

	def test_its_user_can_write_a_view_an_administrator_made_for_them(self):
		view = make_view(user=self.member).insert(ignore_permissions=True)

		frappe.set_user(self.member)
		view.reload()
		view.label = "Renamed"
		view.save()

		self.assertEqual(frappe.db.get_value("Saved View", view.name, "label"), "Renamed")

	def test_a_shared_view_keeps_the_owner_it_was_written_by(self):
		view = make_view().insert(ignore_permissions=True)

		self.assertEqual(view.user, None)
		self.assertEqual(view.owner, "Administrator")

	def test_a_manager_can_take_someone_elses_shared_view_private(self):
		"""`owner` is `set_only_once`, so the invariant is established at insert and never
		re-assigned -- otherwise this move throws `CannotChangeConstantError`."""
		view = make_view().insert(ignore_permissions=True)
		self.assertEqual(view.owner, "Administrator")

		frappe.set_user(self.manager)
		move_view(view.name, shared=False)

		stored = frappe.db.get_value("Saved View", view.name, ["owner", "user"], as_dict=True)
		self.assertEqual(stored.user, self.manager)
		self.assertEqual(stored.owner, "Administrator")


class TestSharedControlComesFromPermissionRows(IntegrationTestCase):
	"""Who manages the shared area is whoever holds write without `if_owner` -- a row an
	administrator adds in the Role Permission Manager, not a constant or a hook."""

	ROLE = "Saved View Test Manager"

	def setUp(self):
		if not frappe.db.exists("Role", self.ROLE):
			frappe.get_doc({"doctype": "Role", "role_name": self.ROLE, "desk_access": 1}).insert(
				ignore_permissions=True
			)
		self.member = make_user("saved-view-rows@example.com", ["Desk User", self.ROLE])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		frappe.clear_cache()

	def grant_shared_control(self, doctype):
		"""What an administrator ticking Write on a new row in the Role Permission Manager does."""
		from frappe.permissions import add_permission

		add_permission(doctype, self.ROLE, 0, "write")
		frappe.clear_cache(doctype=doctype)
		frappe.local.role_permissions = {}

	def test_a_desk_user_does_not_manage_the_shared_area(self):
		frappe.set_user(self.member)

		self.assertFalse(can_manage_shared("Saved View"))
		self.assertFalse(can_manage_shared("Navigation Section"))

	def test_a_role_granted_plain_write_manages_that_doctype(self):
		self.grant_shared_control("Saved View")
		frappe.set_user(self.member)

		self.assertTrue(can_manage_shared("Saved View"))

	def test_the_grant_does_not_leak_to_the_other_doctype(self):
		"""Each DocType's rows answer for itself, or a sidebar grant would be one nobody asked for."""
		self.grant_shared_control("Saved View")
		frappe.set_user(self.member)

		self.assertFalse(can_manage_shared("Navigation Section"))

	def test_the_navigation_section_grant_stands_on_its_own(self):
		self.grant_shared_control("Navigation Section")
		frappe.set_user(self.member)

		self.assertTrue(can_manage_shared("Navigation Section"))
		self.assertFalse(can_manage_shared("Saved View"))
