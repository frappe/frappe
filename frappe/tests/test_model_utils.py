import unittest

import frappe
from frappe.model import is_default_field
from frappe.model.utils import get_fetch_values


class TestModelUtils(unittest.TestCase):
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

		self.assertEqual(
			get_fetch_values(doctype, "assigned_by", user), {"assigned_by_full_name": full_name}
		)

	def test_is_default_field(self):
		self.assertTrue(is_default_field("doctype"))
		self.assertTrue(is_default_field("name"))
		self.assertTrue(is_default_field("owner"))

		self.assertFalse(is_default_field({}))
		self.assertFalse(is_default_field("qwerty1234"))
		self.assertFalse(is_default_field(True))
		self.assertFalse(is_default_field(42))
