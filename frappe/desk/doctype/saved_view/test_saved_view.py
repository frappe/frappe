# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
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
