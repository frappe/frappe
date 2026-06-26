# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import json

import frappe
from frappe.desk.doctype.list_filter.list_filter import (
	compute_route_signature,
	delete_list_filter,
	update_list_filter,
)
from frappe.tests import UnitTestCase
from frappe.tests.utils import toggle_test_mode

LIST_FILTER_OWNER = "list_filter_owner@example.com"
LIST_FILTER_OTHER = "list_filter_other@example.com"


class TestListFilter(UnitTestCase):
	def setUp(self):
		toggle_test_mode(True)
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.db.delete("List Filter", {"filter_name": ["like", "_test_filter_%"]})
		frappe.db.delete("List Filter", {"filter_name": ["like", "_cypress_layout_%"]})
		for email in (LIST_FILTER_OWNER, LIST_FILTER_OTHER):
			if frappe.db.exists("User", email):
				frappe.delete_doc("User", email, force=True, ignore_permissions=True)
		frappe.set_user("Administrator")

	def _create_filter(self, **kwargs):
		doc = frappe.get_doc(
			{
				"doctype": "List Filter",
				"filter_name": kwargs.get("filter_name", "_test_filter_user"),
				"reference_doctype": "ToDo",
				"for_user": kwargs.get("for_user", frappe.session.user),
				"filters": kwargs.get("filters", json.dumps([["ToDo", "status", "=", "Open"]])),
				"columns": kwargs.get("columns", json.dumps([{"fieldname": "status", "label": "Status"}])),
				"sort_field": kwargs.get("sort_field", "modified"),
				"sort_order": kwargs.get("sort_order", "desc"),
			}
		).insert(ignore_permissions=True)
		return doc

	def test_user_can_update_own_filter(self):
		doc = self._create_filter()
		updated = update_list_filter(
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

	def test_non_admin_cannot_reassign_filter_to_other_user(self):
		owner = self._ensure_desk_user(LIST_FILTER_OWNER)
		other = self._ensure_desk_user(LIST_FILTER_OTHER)
		doc = self._create_filter(for_user=owner)

		frappe.set_user(owner)
		self.assertRaises(
			frappe.PermissionError,
			update_list_filter,
			doc.name,
			for_user=other,
		)

	def test_insert_sanitizes_invalid_fields(self):
		doc = frappe.get_doc(
			{
				"doctype": "List Filter",
				"filter_name": "_test_filter_insert_sanitize",
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

	def test_insert_strips_html_from_filter_name(self):
		doc = frappe.get_doc(
			{
				"doctype": "List Filter",
				"filter_name": "_test_filter_xss<script>alert(1)</script>",
				"reference_doctype": "ToDo",
				"for_user": frappe.session.user,
				"filters": "[]",
			}
		).insert(ignore_permissions=True)
		self.assertEqual(doc.filter_name, "_test_filter_xssalert(1)")

	def test_non_admin_cannot_update_global_filter(self):
		doc = self._create_filter(filter_name="_test_filter_global", for_user="")
		email = self._ensure_desk_user(LIST_FILTER_OWNER)
		frappe.set_user(email)
		self.assertRaises(frappe.PermissionError, update_list_filter, doc.name, sort_field="modified")

	def test_delete_own_filter(self):
		doc = self._create_filter(filter_name="_test_filter_delete")
		delete_list_filter(doc.name)
		self.assertFalse(frappe.db.exists("List Filter", doc.name))

	def test_admin_can_update_global_filter(self):
		doc = self._create_filter(filter_name="_test_filter_global_admin", for_user="")
		updated = update_list_filter(doc.name, sort_order="asc")
		self.assertEqual(updated["sort_order"], "asc")

	def test_before_save_sets_route_signature(self):
		doc = self._create_filter()
		self.assertEqual(doc.route_signature, "status=Open")

	def test_before_save_empty_filters_gives_empty_route_signature(self):
		doc = self._create_filter(
			filter_name="_test_filter_empty_sig",
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
		doc = self._create_filter()
		new_columns = [{"fieldname": "status", "label": "Status", "width": 120}]
		updated = update_list_filter(doc.name, columns=json.dumps(new_columns))
		self.assertEqual(json.loads(updated["columns"]), new_columns)

	def test_sanitize_filters_drops_invalid_field(self):
		doc = self._create_filter()
		updated = update_list_filter(
			doc.name,
			filters=json.dumps([["ToDo", "invalid_field_xyz", "=", "x"]]),
		)
		self.assertEqual(json.loads(updated["filters"]), [])
		self.assertEqual(updated["route_signature"], "")

	def test_sanitize_columns_drops_invalid_field(self):
		doc = self._create_filter()
		updated = update_list_filter(
			doc.name,
			columns=json.dumps([{"fieldname": "invalid_field_xyz", "label": "Bad"}]),
		)
		self.assertEqual(json.loads(updated["columns"]), [])

	def test_sanitize_sort_field_clears_invalid_sort(self):
		doc = self._create_filter()
		updated = update_list_filter(doc.name, sort_field="invalid_sort_field_xyz")
		self.assertIsNone(updated["sort_field"])
		self.assertIsNone(updated["sort_order"])

	def test_cypress_test_filter_helpers(self):
		from frappe.tests.ui_test_helpers import (
			clear_list_layout_test_layouts,
			create_list_layout_test_layout,
		)

		filter_name = create_list_layout_test_layout(
			filter_name="_cypress_layout_api_test",
			filters="[]",
		)
		self.assertTrue(frappe.db.exists("List Filter", filter_name))

		doc = frappe.get_doc("List Filter", filter_name)
		self.assertEqual(doc.route_signature, "")
		self.assertEqual(json.loads(doc.filters), [])

		clear_list_layout_test_layouts()
		self.assertFalse(frappe.db.exists("List Filter", filter_name))
