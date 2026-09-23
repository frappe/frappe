# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import operator

import frappe
from frappe.desk.form.activity import get_activity_timeline, parse_visible_types, readable_permlevels
from frappe.desk.form.activity_page import MAX_PAGE_SIZE, ActivityPage
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


def keys(rows: list[dict]) -> list[str]:
	return [r["key"] for r in rows]


class TestActivityPage(FrappeTestCase):
	def test_a_short_feed_is_one_page(self):
		page = ActivityPage(None, 3)
		built = page.build([row("2026-01-02", "comment:b"), row("2026-01-01", "comment:a")])
		self.assertEqual(keys(built["activities"]), ["comment:a", "comment:b"])
		self.assertIsNone(built["next"])

	def test_a_long_feed_stops_at_the_limit_and_points_at_its_oldest_row(self):
		page = ActivityPage(None, 2)
		built = page.build([row(f"2026-01-0{i}", f"log:{i}") for i in range(1, 5)])
		self.assertEqual(keys(built["activities"]), ["log:3", "log:4"])
		self.assertEqual(built["next"], "2026-01-03|log:3")

	def test_the_cursor_keeps_only_older_rows(self):
		page = ActivityPage("2026-01-03 00:00:00|log:3", 5)
		built = page.build([row(f"2026-01-0{i} 00:00:00", f"log:{i}") for i in range(1, 5)])
		self.assertEqual(keys(built["activities"]), ["log:1", "log:2"])
		self.assertEqual(page.filters(), [["creation", "<=", "2026-01-03 00:00:00"]])

	def test_a_cursor_with_an_empty_key_leaves_out_its_instant(self):
		page = ActivityPage("2026-01-03 00:00:00|", 5)
		self.assertEqual(page.filters(), [["creation", "<", "2026-01-03 00:00:00"]])

	def test_a_source_cut_short_holds_the_page_at_its_oldest_kept_row(self):
		page = ActivityPage(None, 2)
		emails = page.trim(
			[row("2026-01-05", "email:c"), row("2026-01-04", "email:b"), row("2026-01-01", "email:a")],
			timestamp,
			lambda at: self.fail("the source was not cut inside one instant"),
		)
		built = page.build([*emails, row("2026-01-03", "comment:x")])
		# comment:x is older than the email the source did not send, so it waits for the next page
		self.assertEqual(keys(built["activities"]), ["email:b", "email:c"])
		self.assertEqual(built["next"], "2026-01-04|")

	def test_a_cut_through_one_instant_reads_the_rest_of_that_instant(self):
		source = [row("2026-01-05", "log:d"), row("2026-01-04", "log:c"), row("2026-01-04", "log:b")]
		source.append(row("2026-01-04", "log:a"))
		page = ActivityPage(None, 2)
		kept = page.trim(source[:3], timestamp, lambda at: [r for r in source if r["timestamp"] == at])
		self.assertEqual(keys(kept), ["log:d", "log:c", "log:b", "log:a"])
		self.assertEqual(page.floor, ("2026-01-04", ""))

	def test_more_rows_in_one_instant_than_the_limit_are_walked_once(self):
		source = [row("2026-01-05 00:00:00", f"log:{key}") for key in "abcde"]
		source += [row("2026-01-06 00:00:00", "log:f"), row("2026-01-04 00:00:00", "log:0")]
		pages = walk(source, limit=2)
		self.assertEqual(sorted(key for page in pages for key in page), sorted(keys(source)))
		self.assertEqual(sum(len(page) for page in pages), len(source))

	def test_a_malformed_cursor_is_rejected(self):
		self.assertRaises(frappe.ValidationError, ActivityPage, "2026-01-01", 2)

	def test_a_cursor_that_is_not_a_string_is_rejected(self):
		self.assertRaises(frappe.ValidationError, ActivityPage, ["2026-01-01 00:00:00|log:a"], 2)

	def test_a_cursor_whose_timestamp_is_not_a_date_is_rejected(self):
		self.assertRaises(frappe.ValidationError, ActivityPage, "yesterday|log:a", 2)

	def test_a_cursor_with_a_timezone_is_rejected(self):
		for cursor in ("2026-01-01 00:00:00+05:30|log:a", "2026-01-01T00:00:00Z|log:a"):
			self.assertRaises(frappe.ValidationError, ActivityPage, cursor, 2)

	def test_the_limit_is_capped(self):
		self.assertEqual(ActivityPage(None, 500).limit, MAX_PAGE_SIZE)


def timestamp(activity: dict) -> str:
	return activity["timestamp"]


def walk(source: list[dict], limit: int) -> list[list[str]]:
	"""Every page's keys, reading `source` the way a database query would."""
	pages, before = [], None
	for _page in range(len(source) + 2):
		page = ActivityPage(before, limit)
		rows = page.trim(
			read(source, page), timestamp, lambda at: [r for r in source if r["timestamp"] == at]
		)
		built = page.build(rows)
		pages.append(keys(built["activities"]))
		if not (before := built["next"]):
			return pages
	raise AssertionError(f"the cursor never reached the end: {pages}")


def read(source: list[dict], page: ActivityPage) -> list[dict]:
	allowed = [r for r in source if all(COMPARE[op](r["timestamp"], at) for _, op, at in page.filters())]
	return sorted(allowed, key=timestamp, reverse=True)[: page.fetch_size]


COMPARE = {"<": operator.lt, "<=": operator.le}


class TestEmailActivities(FrappeTestCase):
	def test_an_email_with_no_date_is_walked_once_at_its_creation(self):
		todo = new_todo()
		sent = [add_email(todo, f"2026-01-0{day} 10:00:00") for day in range(1, 6)]
		undated = add_email(todo, "2026-01-02 10:00:00")
		frappe.db.set_value(
			"Communication",
			undated,
			{"communication_date": None, "creation": "2026-01-03 12:00:00"},
			update_modified=False,
		)

		walked = walk_emails(todo, limit=2)

		self.assertCountEqual(walked, [f"email:{name}" for name in [*sent, undated]])

	def test_an_email_linked_to_the_record_is_read_once(self):
		todo, elsewhere = new_todo(), new_todo()
		sent = add_email(todo, "2026-01-01 10:00:00")
		linked = add_email(elsewhere, "2026-01-02 10:00:00", linked_to=todo)
		sent_and_linked = add_email(todo, "2026-01-03 10:00:00", linked_to=todo)
		oldest_first = [f"email:{name}" for name in (sent, linked, sent_and_linked)]

		read = get_activity_timeline("ToDo", todo.name, ["email"])

		self.assertEqual(keys(read["activities"]), oldest_first)
		self.assertEqual(walk_emails(todo, limit=1), oldest_first[::-1])

	def test_emails_sharing_one_instant_are_walked_once(self):
		todo = new_todo()
		same_instant = [add_email(todo, "2026-01-01 10:00:00") for _email in range(3)]

		walked = walk_emails(todo, limit=2)

		self.assertCountEqual(walked, [f"email:{name}" for name in same_instant])


def new_todo():
	return frappe.get_doc({"doctype": "ToDo", "description": "emails"}).insert()


def walk_emails(todo, limit: int) -> list[str]:
	"""The email keys of every page of the ToDo's feed, newest first."""
	walked, before = [], None
	for _page in range(20):
		built = get_activity_timeline("ToDo", todo.name, ["email"], limit=limit, before=before)
		walked += reversed(keys(built["activities"]))
		if not (before := built["next"]):
			return walked
	raise AssertionError(f"the cursor never reached the end: {walked}")


def add_email(reference, communication_date: str, linked_to=None) -> str:
	email = frappe.get_doc(
		{
			"doctype": "Communication",
			"communication_type": "Communication",
			"communication_medium": "Email",
			"sent_or_received": "Received",
			"subject": f"sent {communication_date}",
			"sender": "someone@example.com",
			"communication_date": communication_date,
			"reference_doctype": "ToDo",
			"reference_name": reference.name,
		}
	)
	if linked_to:
		email.add_link("ToDo", linked_to.name)
	return email.insert(ignore_permissions=True).name
