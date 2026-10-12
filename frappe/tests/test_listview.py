# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json

import frappe
from frappe.desk.listview import get_group_by_count, get_list_settings, set_list_settings
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
		self.assertEqual(data, [{"name": "Administrator", "count": 1}])

	def test_get_group_by_invalid_field(self):
		self.assertRaises(
			ValueError,
			get_group_by_count,
			"Note",
			'[["Note Seen By","user","=","Administrator"]]',
			"invalid_field",
		)

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
