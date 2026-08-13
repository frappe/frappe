# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.doctype.page_script.page_script import get_page_scripts, reorder
from frappe.desk.doctype.saved_view.test_api import make_user
from frappe.tests import IntegrationTestCase


def make_script(name, **kwargs):
	values = {
		"doctype": "Page Script",
		"__newname": name,
		"dt": "Note",
		"view": "Record",
		"script": "export default {}",
	}
	values.update(kwargs)
	return frappe.get_doc(values)


def run_order(name):
	return frappe.db.get_value("Page Script", name, "run_order")


class TestPageScript(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_returns_enabled_scripts_in_run_order(self):
		make_script("first-note-script").insert()
		make_script("second-note-script").insert()
		make_script("disabled-note-script", enabled=0).insert()
		reorder("Note", "Record", ["second-note-script", "first-note-script"])

		names = [row["name"] for row in get_page_scripts("Note", "Record")["scripts"]]
		self.assertEqual(names, ["second-note-script", "first-note-script"])

	def test_falls_back_to_creation_order_when_nobody_has_chosen(self):
		# Every script sits on the default 0, so they all tie and `creation asc` decides
		# — which is exactly what an existing site looks like the moment it migrates.
		make_script("first-note-script").insert()
		make_script("second-note-script").insert()

		names = [row["name"] for row in get_page_scripts("Note", "Record")["scripts"]]
		self.assertEqual(names, ["first-note-script", "second-note-script"])

	def test_scopes_to_the_doctype(self):
		make_script("note-script").insert()
		make_script("todo-script", dt="ToDo").insert()

		names = [row["name"] for row in get_page_scripts("ToDo", "Record")["scripts"]]
		self.assertEqual(names, ["todo-script"])

	def test_rejects_an_unknown_view(self):
		self.assertRaises(frappe.ValidationError, get_page_scripts, "Note", "List")

	def test_rejects_a_doctype_filter_posing_as_a_name(self):
		make_script("note-script").insert()
		self.assertRaises(frappe.FrappeTypeError, get_page_scripts, ["!=", ""], "Record")

	def test_reports_write_access_for_the_toast_gate(self):
		self.assertTrue(get_page_scripts("Note", "Record")["can_write"])


class TestReorder(IntegrationTestCase):
	def setUp(self):
		for name in ("a-note-script", "b-note-script", "c-note-script"):
			make_script(name).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_renumbers_densely_from_one(self):
		reorder("Note", "Record", ["c-note-script", "a-note-script", "b-note-script"])

		self.assertEqual(run_order("c-note-script"), 1)
		self.assertEqual(run_order("a-note-script"), 2)
		self.assertEqual(run_order("b-note-script"), 3)

	def test_leaves_modified_alone_so_the_script_lock_still_means_the_text_changed(self):
		before = frappe.db.get_value("Page Script", "a-note-script", "modified")
		reorder("Note", "Record", ["c-note-script", "b-note-script", "a-note-script"])

		self.assertEqual(frappe.db.get_value("Page Script", "a-note-script", "modified"), before)

	def test_tolerates_a_name_the_list_had_not_seen_yet(self):
		# The ordinary concurrent create: someone else's new script is not in the list
		# that was dragged. It keeps its own number rather than failing the drag.
		frappe.db.set_value("Page Script", "c-note-script", "run_order", 9, update_modified=False)
		reorder("Note", "Record", ["b-note-script", "a-note-script"])

		self.assertEqual(run_order("b-note-script"), 1)
		self.assertEqual(run_order("a-note-script"), 2)
		self.assertEqual(run_order("c-note-script"), 9)

	def test_rejects_a_name_from_another_doctypes_list(self):
		make_script("todo-script", dt="ToDo").insert()

		with self.assertRaises(frappe.ValidationError):
			reorder("Note", "Record", ["a-note-script", "todo-script"])

	def test_rejects_a_name_that_does_not_exist(self):
		with self.assertRaises(frappe.ValidationError):
			reorder("Note", "Record", ["a-note-script", "no-such-script"])

	def test_rejects_a_duplicate(self):
		with self.assertRaises(frappe.ValidationError):
			reorder("Note", "Record", ["a-note-script", "a-note-script", "b-note-script"])

	def test_rejects_an_unknown_view(self):
		with self.assertRaises(frappe.ValidationError):
			reorder("Note", "List", ["a-note-script"])

	def test_rejects_names_that_are_not_a_list_of_strings(self):
		# The whitelist's type hints catch this before the method's own isinstance
		# guard does, exactly as they do for `dt` on get_page_scripts.
		with self.assertRaises(frappe.FrappeTypeError):
			reorder("Note", "Record", [["!=", ""]])

	def test_refuses_an_author_without_write_on_page_script(self):
		# Page Script grants write to System Manager only.
		frappe.set_user(make_user("page-script-reader@example.com", ["Desk User"]))

		with self.assertRaises(frappe.PermissionError):
			reorder("Note", "Record", ["c-note-script", "a-note-script", "b-note-script"])

	def test_does_not_renumber_when_one_name_is_bad(self):
		with self.assertRaises(frappe.ValidationError):
			reorder("Note", "Record", ["a-note-script", "no-such-script"])

		self.assertEqual(run_order("a-note-script"), 0)
