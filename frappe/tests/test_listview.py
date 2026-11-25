# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json

import frappe
from frappe.desk.listview import (
	get_assignee_groups,
	get_group_by_count,
	get_list_settings,
	set_list_settings,
)
from frappe.desk.reportview import get
from frappe.tests import IntegrationTestCase


class TestListView(IntegrationTestCase):
	def setUp(self):
		if frappe.db.exists("List View Settings", "DocType"):
			frappe.delete_doc("List View Settings", "DocType")

	def test_get_list_settings_without_settings(self):
		self.assertIsNone(get_list_settings("DocType"), None)

	def test_get_list_settings_with_default_settings(self):
		frappe.get_doc({"doctype": "List View Settings", "name": "DocType"}).insert()
		settings = get_list_settings("DocType")
		self.assertIsNotNone(settings)

		self.assertEqual(settings.disable_auto_refresh, 0)
		self.assertEqual(settings.disable_count, 0)
		self.assertEqual(settings.disable_comment_count, 0)
		self.assertEqual(settings.disable_sidebar_stats, 0)

	def test_get_list_settings_with_non_default_settings(self):
		frappe.get_doc({"doctype": "List View Settings", "name": "DocType", "disable_count": 1}).insert()
		settings = get_list_settings("DocType")
		self.assertIsNotNone(settings)

		self.assertEqual(settings.disable_auto_refresh, 0)
		self.assertEqual(settings.disable_count, 1)
		self.assertEqual(settings.disable_comment_count, 0)
		self.assertEqual(settings.disable_sidebar_stats, 0)

	def test_set_list_settings_without_settings(self):
		set_list_settings("DocType", json.dumps({}))
		settings = frappe.get_doc("List View Settings", "DocType")

		self.assertEqual(settings.disable_auto_refresh, 0)
		self.assertEqual(settings.disable_count, 0)
		self.assertEqual(settings.disable_comment_count, 0)
		self.assertEqual(settings.disable_sidebar_stats, 0)

	def test_set_list_settings_with_existing_settings(self):
		frappe.get_doc({"doctype": "List View Settings", "name": "DocType", "disable_count": 1}).insert()
		set_list_settings("DocType", json.dumps({"disable_count": 0, "disable_auto_refresh": 1}))
		settings = frappe.get_doc("List View Settings", "DocType")

		self.assertEqual(settings.disable_auto_refresh, 1)
		self.assertEqual(settings.disable_count, 0)
		self.assertEqual(settings.disable_comment_count, 0)
		self.assertEqual(settings.disable_sidebar_stats, 0)

	def test_list_view_child_table_filter_with_created_by_filter(self):
		if frappe.db.exists("Note", "Test created by filter with child table filter"):
			frappe.delete_doc("Note", "Test created by filter with child table filter")

		doc = frappe.get_doc(
			{"doctype": "Note", "title": "Test created by filter with child table filter", "public": 1}
		)
		doc.append("seen_by", {"user": "Administrator"})
		doc.insert()

		data = {
			d.name: d.count
			for d in get_group_by_count("Note", '[["Note Seen By","user","=","Administrator"]]', "owner")
		}
		self.assertEqual(data["Administrator"], 1)

	def test_assigned_to_count_on_autoincrement_doctype(self):
		job = frappe.get_doc(
			doctype="MapReduce Job", job_name="Test assigned to count", map="m", reduce="r", data="[]"
		).insert()
		todo = frappe.get_doc(
			doctype="ToDo",
			description="Test assigned to count",
			allocated_to="Administrator",
			reference_type="MapReduce Job",
			reference_name=job.name,
		).insert()
		# same reference name, another doctype: must not be counted
		other_todo = frappe.copy_doc(todo).insert()
		frappe.db.set_value("ToDo", other_todo.name, "reference_type", "MapReduce Task")

		data = get_group_by_count("MapReduce Job", [["name", "=", job.name]], "assigned_to")
		full_name, email = frappe.db.get_value("User", "Administrator", ["full_name", "email"])
		self.assertEqual(
			data,
			[
				{
					"name": "Administrator",
					"count": 1,
					"title": full_name,
					"search_text": f"{full_name} {email}",
				}
			],
		)

	def test_owner_count_carries_search_field_values(self):
		frappe.get_doc({"doctype": "Note", "title": "Test owner search text", "public": 1}).insert()

		data = get_group_by_count("Note", [["title", "=", "Test owner search text"]], "owner")
		full_name, email = frappe.db.get_value("User", "Administrator", ["full_name", "email"])
		self.assertEqual(data[0].search_text, f"{full_name} {email}")

	def test_assigned_to_count_leaves_out_closed_assignments(self):
		job = frappe.get_doc(
			doctype="MapReduce Job", job_name="Test closed assignment", map="m", reduce="r", data="[]"
		).insert()
		frappe.get_doc(
			doctype="ToDo",
			description="Test closed assignment",
			allocated_to="Administrator",
			reference_type="MapReduce Job",
			reference_name=job.name,
			status="Closed",
		).insert()

		data = get_group_by_count("MapReduce Job", [["name", "=", job.name]], "assigned_to")
		self.assertEqual(data, [])

	def test_get_group_by_invalid_field(self):
		self.assertRaises(
			ValueError,
			get_group_by_count,
			"Note",
			'[["Note Seen By","user","=","Administrator"]]',
			"invalid_field",
		)

	def _assigned_jobs(self, *assignees: list[str]) -> list[str]:
		"""One MapReduce Job per list of users, each assigned to those users; returns the names."""
		names = []
		for users in assignees:
			job = frappe.get_doc(
				doctype="MapReduce Job", job_name="Test assignee groups", map="m", reduce="r", data="[]"
			).insert()
			for user in users:
				frappe.get_doc(
					doctype="ToDo",
					description="Test assignee groups",
					allocated_to=user,
					reference_type="MapReduce Job",
					reference_name=job.name,
				).insert()
			names.append(job.name)
		return names

	def test_assignee_groups_count_a_record_under_each_assignee(self):
		names = self._assigned_jobs(["Administrator", "Guest"], ["Administrator"], [])
		rows = get_assignee_groups(
			"MapReduce Job",
			["_assign", {"COUNT": "name", "as": "_aggregate_0"}],
			"_assign",
			[["name", "in", names]],
		)
		self.assertCountEqual(
			rows,
			[
				{"_assign": "Administrator", "_aggregate_0": 2},
				{"_assign": "Guest", "_aggregate_0": 1},
				{"_assign": None, "_aggregate_0": 1},
			],
		)

	def test_assignee_groups_leave_out_closed_assignments(self):
		names = self._assigned_jobs(["Administrator"], ["Guest"])
		frappe.db.set_value(
			"ToDo", {"reference_name": names[1], "reference_type": "MapReduce Job"}, "status", "Closed"
		)
		rows = get_assignee_groups("MapReduce Job", ["_assign"], "_assign", [["name", "in", names]])
		self.assertCountEqual(rows, [{"_assign": "Administrator"}, {"_assign": None}])

	def test_assignee_groups_leave_out_tasks_without_an_assignee(self):
		names = self._assigned_jobs(["Administrator"])
		frappe.get_doc(
			doctype="ToDo",
			description="Test assignee groups",
			reference_type="MapReduce Job",
			reference_name=names[0],
		).insert()
		rows = get_assignee_groups("MapReduce Job", ["_assign"], "_assign", [["name", "in", names]])
		self.assertEqual(rows, [{"_assign": "Administrator"}])

	def test_assignee_groups_sort_and_page_in_the_query(self):
		names = self._assigned_jobs(["Guest"], ["Administrator", "Guest"])
		rows = get_assignee_groups(
			"MapReduce Job",
			["job_name", "_assign", {"COUNT": "name", "as": "_aggregate_0"}],
			"job_name, _assign",
			[["name", "in", names]],
			"_aggregate_0 desc, _assign asc",
			limit_page_length=1,
		)
		self.assertEqual(rows, [{"job_name": "Test assignee groups", "_assign": "Guest", "_aggregate_0": 2}])
		next_page = get_assignee_groups(
			"MapReduce Job",
			["_assign"],
			"_assign",
			[["name", "in", names]],
			"_assign desc",
			limit_start=1,
			limit_page_length=1,
		)
		self.assertEqual(next_page, [{"_assign": "Administrator"}])

	def test_assignee_groups_reject_unsafe_input(self):
		for fields, group_by, order_by in (
			(["status"], "status", None),
			([{"SLEEP": "name", "as": "x"}], "_assign", None),
			([{"COUNT": "name", "as": "x y"}], "_assign", None),
			(["_assign"], "_assign", "creation desc"),
		):
			with self.assertRaises(frappe.ValidationError):
				get_assignee_groups("MapReduce Job", fields, group_by, order_by=order_by)

	def test_list_view_comment_count(self):
		frappe.form_dict.doctype = "DocType"
		frappe.form_dict.limit = "1"
		frappe.form_dict.fields = [
			"`tabDocType`.`name`",
		]

		for with_comment_count in (1, True, "1"):
			frappe.form_dict.with_comment_count = with_comment_count
			self.assertEqual(len(get()["values"][0]), 2)

		for with_comment_count in (0, False, "0", None):
			frappe.form_dict.with_comment_count = with_comment_count
			self.assertEqual(len(get()["values"][0]), 1)
