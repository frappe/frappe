# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.desk.form.activity import parse_visible_types, readable_permlevels
from frappe.tests.utils import FrappeTestCase


class TestParseVisibleTypes(FrappeTestCase):
	def test_empty_means_no_filter(self):
		self.assertEqual(parse_visible_types(None), (None, None))
		self.assertEqual(parse_visible_types([]), (None, None))

	def test_types_and_version_fields(self):
		types, fields = parse_visible_types(["email", "comment", {"version": ["status", "priority"]}])
		self.assertEqual(types, {"email", "comment", "version"})
		self.assertEqual(fields, ["status", "priority"])

	def test_malformed_entries_are_ignored(self):
		# non-string entries and a non-list field value must not become filters
		types, fields = parse_visible_types([1, "email", {"version": "status"}])
		self.assertEqual(types, {"email", "version"})
		self.assertIsNone(fields)

	def test_all_malformed_means_no_filter(self):
		self.assertEqual(parse_visible_types([42, True]), (None, None))

	def test_non_string_fields_are_dropped(self):
		_types, fields = parse_visible_types([{"version": ["status", 5, None]}])
		self.assertEqual(fields, ["status"])


class TestReadablePermlevels(FrappeTestCase):
	def test_permlevel_zero_readable_with_permission_rows(self):
		levels = readable_permlevels(frappe.get_meta("User"))
		self.assertIsNotNone(levels)
		self.assertIn(0, levels)

	def test_no_permission_rows_means_unrestricted(self):
		# child doctypes carry no permission rows of their own
		self.assertIsNone(readable_permlevels(frappe.get_meta("DocField")))
