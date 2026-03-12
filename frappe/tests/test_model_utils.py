from contextlib import contextmanager
from random import choice

import frappe
import frappe.share
from frappe.model import core_doctypes_list, get_permitted_fields, is_default_field
from frappe.model.utils import get_fetch_values
from frappe.tests import IntegrationTestCase


class TestModelUtils(IntegrationTestCase):
	def test_get_fetch_values(self):
		doctype = "ToDo"

		# no fields to fetch
		self.assertEqual(get_fetch_values(doctype, "role", "System Manager"), {})

		# no value
		self.assertEqual(get_fetch_values(doctype, "assigned_by", None), {"assigned_by_full_name": None})

		# no db values
		self.assertEqual(
			get_fetch_values(doctype, "assigned_by", "~not-a-user~"), {"assigned_by_full_name": None}
		)

		# valid db values
		user = "test@example.com"
		full_name = frappe.db.get_value("User", user, "full_name")

		self.assertEqual(get_fetch_values(doctype, "assigned_by", user), {"assigned_by_full_name": full_name})

	def test_get_permitted_fields(self):
		# Administrator should have access to all fields in ToDo
		todo_all_fields = get_permitted_fields("ToDo", user="Administrator")
		todo_all_columns = frappe.get_meta("ToDo").get_valid_columns()
		self.assertListEqual(todo_all_fields, todo_all_columns)

		# Guest should have access to no non-std fields in ToDo
		with set_user("Guest"):
			guest_permitted_fields = get_permitted_fields("ToDo")
			self.assertNotIn("description", guest_permitted_fields)

		# everyone should have access to all fields of core doctypes
		with set_user("Guest"):
			picked_doctype = choice(core_doctypes_list)
			core_permitted_fields = get_permitted_fields(picked_doctype)
			picked_doctype_all_columns = frappe.get_meta(picked_doctype).get_valid_columns()
			self.assertSequenceEqual(core_permitted_fields, picked_doctype_all_columns)

		# access to child tables' fields is restricted to no fields unless parent is passed & permitted
		with set_user("Administrator"):
			without_parent_fields = get_permitted_fields("Installed Application")
			with_parent_fields = get_permitted_fields(
				"Installed Application", parenttype="Installed Applications"
			)
			child_all_fields = frappe.get_meta("Installed Application").get_valid_columns()
			self.assertLess(len(without_parent_fields), len(with_parent_fields))
			self.assertSequenceEqual(set(with_parent_fields), set(child_all_fields))

		# guest has access to no non-std fields
		with set_user("Guest"):
			self.assertNotIn("app_name", get_permitted_fields("Installed Application"))
			self.assertNotIn(
				"app_name", get_permitted_fields("Installed Application", parenttype="Installed Applications")
			)

	def test_get_permitted_fields_for_child_table_via_docshare(self):
		user = "test2@example.com"

		doc = frappe.get_doc(
			{
				"doctype": "Web Page",
				"title": "test child table share",
				"page_blocks": [{"web_template": "Hero with Right Image"}],
			}
		).insert()

		try:
			# user without Website Manager role has no access to child table fields
			with set_user(user):
				child_fields = get_permitted_fields(
					"Web Page Block", parenttype="Web Page", permission_type="read"
				)
				self.assertNotIn("web_template", child_fields)

			frappe.share.add("Web Page", doc.name, user)

			# sharing parent grants access to child table fields
			with set_user(user):
				child_fields = get_permitted_fields(
					"Web Page Block", parenttype="Web Page", permission_type="read"
				)
				self.assertIn("web_template", child_fields)
				self.assertIn("css_class", child_fields)

			# child table fields are also accessible via get_list
			with set_user(user):
				result = frappe.get_list(
					"Web Page",
					fields=["name", "`tabWeb Page Block`.web_template"],
					limit=5,
				)
				matched = [r for r in result if r.get("name") == doc.name]
				self.assertTrue(matched)
				self.assertEqual(matched[0].get("web_template"), "Hero with Right Image")
		finally:
			frappe.set_user("Administrator")
			frappe.share.remove("Web Page", doc.name, user)
			doc.delete(ignore_permissions=True)

	def test_is_default_field(self):
		self.assertTrue(is_default_field("doctype"))
		self.assertTrue(is_default_field("name"))
		self.assertTrue(is_default_field("owner"))

		self.assertFalse(is_default_field({}))
		self.assertFalse(is_default_field("qwerty1234"))
		self.assertFalse(is_default_field(True))
		self.assertFalse(is_default_field(42))


@contextmanager
def set_user(user: str):
	past_user = frappe.session.user or "Administrator"
	frappe.set_user(user)
	yield
	frappe.set_user(past_user)
