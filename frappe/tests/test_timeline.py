# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.desk.form.activity import parse_visible_types, readable_permlevels
from frappe.desk.form.activity_page import ActivityPage
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


def row(timestamp: str, key: str) -> dict:
	return {"timestamp": timestamp, "key": key}


class TestActivityPage(FrappeTestCase):
	def test_a_short_feed_is_one_page(self):
		page = ActivityPage(None, 3)
		built = page.build([row("2026-01-02", "comment:b"), row("2026-01-01", "comment:a")])
		self.assertEqual([r["key"] for r in built["activities"]], ["comment:a", "comment:b"])
		self.assertIsNone(built["next"])

	def test_a_long_feed_stops_at_the_limit_and_points_at_its_oldest_row(self):
		page = ActivityPage(None, 2)
		built = page.build([row(f"2026-01-0{i}", f"log:{i}") for i in range(1, 5)])
		self.assertEqual([r["key"] for r in built["activities"]], ["log:3", "log:4"])
		self.assertEqual(built["next"], "2026-01-03|log:3")

	def test_the_cursor_keeps_only_older_rows(self):
		page = ActivityPage("2026-01-03|log:3", 5)
		built = page.build([row(f"2026-01-0{i}", f"log:{i}") for i in range(1, 5)])
		self.assertEqual([r["key"] for r in built["activities"]], ["log:1", "log:2"])
		self.assertEqual(page.filters(), [["creation", "<=", "2026-01-03"]])

	def test_a_source_cut_short_holds_the_page_at_its_oldest_kept_row(self):
		page = ActivityPage(None, 2)
		emails = page.trim(
			[row("2026-01-05", "email:c"), row("2026-01-04", "email:b"), row("2026-01-01", "email:a")],
			lambda r: r["timestamp"],
		)
		built = page.build([*emails, row("2026-01-03", "comment:x")])
		# comment:x is older than the email the source did not send, so it waits for the next page
		self.assertEqual([r["key"] for r in built["activities"]], ["email:b", "email:c"])
		self.assertEqual(built["next"], "2026-01-04|")

	def test_a_cut_through_one_instant_leaves_that_instant_to_the_next_page(self):
		page = ActivityPage(None, 2)
		kept = page.trim(
			[row("2026-01-05", "log:c"), row("2026-01-04", "log:b"), row("2026-01-04", "log:a")],
			lambda r: r["timestamp"],
		)
		built = page.build(kept)
		self.assertEqual([r["key"] for r in built["activities"]], ["log:c"])
		self.assertEqual(ActivityPage(built["next"], 2).build(kept[1:])["activities"], [kept[1]])

	def test_a_malformed_cursor_is_rejected(self):
		self.assertRaises(frappe.ValidationError, ActivityPage, "2026-01-01", 2)
