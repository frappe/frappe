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

	def test_json_string_is_parsed(self):
		# form/query transport delivers arguments as JSON strings
		types, fields = parse_visible_types('["email", {"version": ["status"]}]')
		self.assertEqual(types, {"email", "version"})
		self.assertEqual(fields, ["status"])

	def test_unknown_names_are_left_alone(self):
		# unknown types/fields simply match nothing, like an unknown column in get_list
		types, fields = parse_visible_types(["nope", {"version": ["not_a_field", 5]}])
		self.assertEqual(types, {"nope", "version"})
		self.assertEqual(fields, ["not_a_field", 5])

	def test_malformed_shapes_are_rejected(self):
		for bad in (
			"not json",  # transport string must decode
			[{"version": "status"}],  # field list must be a list
			[1],  # entries are strings or maps
			[42, True],
			{"version": ["status"]},  # top level must be a list
		):
			with self.assertRaises(frappe.ValidationError):
				parse_visible_types(bad)


class TestReadablePermlevels(FrappeTestCase):
	def test_permlevel_zero_readable_with_permission_rows(self):
		levels = readable_permlevels(frappe.get_meta("User"))
		self.assertIsNotNone(levels)
		self.assertIn(0, levels)

	def test_no_permission_rows_means_unrestricted(self):
		# child doctypes carry no permission rows of their own
		self.assertIsNone(readable_permlevels(frappe.get_meta("DocField")))
