# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import frappe
from frappe.desk.doctype.todo.todo import ToDo
from frappe.desk.form.activity import (
	activity_text,
	get_activity_timeline,
	parse_visible_types,
	readable_permlevels,
)
from frappe.tests import IntegrationTestCase
from frappe.tests.utils import FrappeTestCase


class TestActivityText(FrappeTestCase):
	def test_html_entities_are_decoded(self):
		self.assertEqual(
			activity_text("added tag Released &amp; removed tag Pending Release"),
			"added tag Released & removed tag Pending Release",
		)


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


def call_log(doc):
	return [
		{
			"type": "call",
			"key": f"call:{doc.name}",
			"timestamp": "2000-01-01 00:00:00",
			"author": {"email": "Administrator", "fullname": "Administrator", "image": None},
			"data": {"name": doc.name, "duration": 60},
		}
	]


class TestControllerActivities(IntegrationTestCase):
	def setUp(self):
		self.todo = frappe.get_doc(doctype="ToDo", description="timeline test").insert()

	def activities(self, visible_types=None):
		return get_activity_timeline("ToDo", self.todo.name, visible_types)["activities"]

	def test_a_controller_without_the_method_adds_nothing(self):
		self.assertFalse(hasattr(ToDo, "get_additional_activities"))
		self.assertEqual({a["type"] for a in self.activities()}, {"log"})

	def test_a_method_that_returns_none_adds_nothing(self):
		expected = self.activities()
		with patch.object(ToDo, "get_additional_activities", lambda doc: None, create=True):
			self.assertEqual(self.activities(), expected)

	def test_controller_rows_join_the_timeline_in_order(self):
		with patch.object(ToDo, "get_additional_activities", call_log, create=True):
			activities = self.activities()

		self.assertEqual(activities[0], call_log(self.todo)[0])
		self.assertEqual(activities[1]["key"], "creation")

	def test_visible_types_filter_controller_rows(self):
		with patch.object(ToDo, "get_additional_activities", call_log, create=True):
			self.assertEqual([a["type"] for a in self.activities(["call"])], ["call"])
			self.assertNotIn("call", {a["type"] for a in self.activities(["log"])})

	def test_a_row_with_a_key_frappe_returned_is_dropped(self):
		creation = self.activities()[0]
		clash = {**creation, "data": {"name": "creation", "subtype": "created", "text": "clash"}}

		with patch.object(ToDo, "get_additional_activities", lambda doc: [clash], create=True):
			activities = self.activities()

		self.assertEqual([a for a in activities if a["key"] == "creation"], [creation])
