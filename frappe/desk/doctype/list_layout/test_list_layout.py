# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import json

import frappe
from frappe.desk.doctype.list_layout.list_layout import (
	compute_route_signature,
	delete_list_layout,
	update_list_layout,
)
from frappe.tests import UnitTestCase
from frappe.tests.utils import toggle_test_mode


class TestListLayout(UnitTestCase):
	def setUp(self):
		toggle_test_mode(True)
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.db.delete("List Layout", {"filter_name": ["like", "_test_layout_%"]})
		frappe.db.delete("List Layout", {"filter_name": ["like", "_cypress_layout_%"]})
		frappe.set_user("Administrator")

	def _create_layout(self, **kwargs):
		doc = frappe.get_doc(
			{
				"doctype": "List Layout",
				"filter_name": kwargs.get("filter_name", "_test_layout_user"),
				"reference_doctype": "ToDo",
				"for_user": kwargs.get("for_user", frappe.session.user),
				"filters": kwargs.get("filters", json.dumps([["ToDo", "status", "=", "Open"]])),
				"columns": kwargs.get("columns", json.dumps([{"fieldname": "status", "label": "Status"}])),
				"sort_field": kwargs.get("sort_field", "modified"),
				"sort_order": kwargs.get("sort_order", "desc"),
			}
		).insert(ignore_permissions=True)
		return doc

	def test_user_can_update_own_layout(self):
		doc = self._create_layout()
		updated = update_list_layout(
			doc.name,
			filters=json.dumps([["ToDo", "status", "=", "Closed"]]),
			sort_field="modified",
			sort_order="asc",
		)
		self.assertEqual(json.loads(updated["filters"])[0][3], "Closed")
		self.assertEqual(updated["sort_order"], "asc")

	def _ensure_desk_user(self, email):
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Test",
					"send_welcome_email": 0,
				}
			).insert(ignore_permissions=True)

		user = frappe.get_doc("User", email)
		user.roles = []
		user.append("roles", {"role": "Desk User"})
		user.save(ignore_permissions=True)
		return email

	def test_non_admin_cannot_reassign_layout_to_other_user(self):
		owner = self._ensure_desk_user("test@example.com")
		other = self._ensure_desk_user("other@example.com")
		doc = self._create_layout(for_user=owner)

		frappe.set_user(owner)
		self.assertRaises(
			frappe.PermissionError,
			update_list_layout,
			doc.name,
			for_user=other,
		)

	def test_insert_sanitizes_invalid_fields(self):
		doc = frappe.get_doc(
			{
				"doctype": "List Layout",
				"filter_name": "_test_layout_insert_sanitize",
				"reference_doctype": "ToDo",
				"for_user": frappe.session.user,
				"filters": json.dumps([["ToDo", "invalid_field_xyz", "=", "x"]]),
				"columns": json.dumps([{"fieldname": "invalid_field_xyz", "label": "Bad"}]),
				"sort_field": "invalid_sort_field_xyz",
				"sort_order": "desc",
			}
		).insert(ignore_permissions=True)

		self.assertEqual(json.loads(doc.filters), [])
		self.assertEqual(json.loads(doc.columns), [])
		self.assertIsNone(doc.sort_field)
		self.assertIsNone(doc.sort_order)

	def test_non_admin_cannot_update_global_layout(self):
		doc = self._create_layout(filter_name="_test_layout_global", for_user="")
		email = self._ensure_desk_user("test@example.com")
		frappe.set_user(email)
		self.assertRaises(frappe.PermissionError, update_list_layout, doc.name, sort_field="modified")

	def test_delete_own_layout(self):
		doc = self._create_layout(filter_name="_test_layout_delete")
		delete_list_layout(doc.name)
		self.assertFalse(frappe.db.exists("List Layout", doc.name))

	def test_admin_can_update_global_layout(self):
		doc = self._create_layout(filter_name="_test_layout_global_admin", for_user="")
		updated = update_list_layout(doc.name, sort_order="asc")
		self.assertEqual(updated["sort_order"], "asc")

	def test_before_save_sets_route_signature(self):
		doc = self._create_layout()
		self.assertEqual(doc.route_signature, "status=Open")

	def test_before_save_empty_filters_gives_empty_route_signature(self):
		doc = self._create_layout(
			filter_name="_test_layout_empty_sig",
			filters="[]",
		)
		self.assertEqual(doc.route_signature, "")

	def test_compute_route_signature_non_equals_operator(self):
		signature = compute_route_signature(
			"ToDo",
			[["ToDo", "modified", ">", "2024-01-01"]],
		)
		self.assertEqual(signature, 'modified=[">","2024-01-01"]')

	def test_update_columns_only(self):
		doc = self._create_layout()
		new_columns = [{"fieldname": "status", "label": "Status", "width": 120}]
		updated = update_list_layout(doc.name, columns=json.dumps(new_columns))
		self.assertEqual(json.loads(updated["columns"]), new_columns)

	def test_sanitize_filters_drops_invalid_field(self):
		doc = self._create_layout()
		updated = update_list_layout(
			doc.name,
			filters=json.dumps([["ToDo", "invalid_field_xyz", "=", "x"]]),
		)
		self.assertEqual(json.loads(updated["filters"]), [])
		self.assertEqual(updated["route_signature"], "")

	def test_sanitize_columns_drops_invalid_field(self):
		doc = self._create_layout()
		updated = update_list_layout(
			doc.name,
			columns=json.dumps([{"fieldname": "invalid_field_xyz", "label": "Bad"}]),
		)
		self.assertEqual(json.loads(updated["columns"]), [])

	def test_sanitize_sort_field_clears_invalid_sort(self):
		doc = self._create_layout()
		updated = update_list_layout(doc.name, sort_field="invalid_sort_field_xyz")
		self.assertIsNone(updated["sort_field"])
		self.assertIsNone(updated["sort_order"])

	def test_cypress_test_layout_helpers(self):
		from frappe.tests.ui_test_helpers import (
			clear_list_layout_test_layouts,
			create_list_layout_test_layout,
		)

		layout_name = create_list_layout_test_layout(
			filter_name="_cypress_layout_api_test",
			filters="[]",
		)
		self.assertTrue(frappe.db.exists("List Layout", layout_name))

		doc = frappe.get_doc("List Layout", layout_name)
		self.assertEqual(doc.route_signature, "")
		self.assertEqual(json.loads(doc.filters), [])

		clear_list_layout_test_layouts()
		self.assertFalse(frappe.db.exists("List Layout", layout_name))
