# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json
import os
import tempfile
from unittest.mock import patch

import frappe
from frappe.custom.doctype.client_script import client_script
from frappe.custom.doctype.client_script.client_script import get_client_scripts, reorder
from frappe.desk.form.meta import get_meta
from frappe.tests import IntegrationTestCase


def make_script(name, **kwargs):
	values = {
		"doctype": "Client Script",
		"__newname": name,
		"dt": "Note",
		"view": "Record",
		"enabled": 1,
		"script": "export default {}",
	}
	values.update(kwargs)
	return frappe.get_doc(values)


def make_user(email, roles):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": email.split("@")[0], "roles": []}
		).insert(ignore_permissions=True)

	user = frappe.get_doc("User", email)
	user.set("roles", [{"role": role} for role in roles])
	user.save(ignore_permissions=True)
	return email


def run_order(name):
	return frappe.db.get_value("Client Script", name, "run_order")


def script_names(dt="Note"):
	return [row["name"] for row in get_client_scripts(dt, "Record")["scripts"]]


class TestClientScriptsForTheRecordView(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_returns_enabled_scripts_in_run_order(self):
		make_script("first-note-script").insert()
		make_script("second-note-script").insert()
		make_script("disabled-note-script", enabled=0).insert()
		reorder("Note", "Record", ["second-note-script", "first-note-script"])

		self.assertEqual(script_names(), ["second-note-script", "first-note-script"])

	def test_falls_back_to_creation_order_when_nobody_has_chosen(self):
		make_script("first-note-script").insert()
		make_script("second-note-script").insert()

		self.assertEqual(script_names(), ["first-note-script", "second-note-script"])

	def test_scopes_to_the_doctype(self):
		make_script("note-script").insert()
		make_script("todo-script", dt="ToDo").insert()

		self.assertEqual(script_names("ToDo"), ["todo-script"])

	def test_ignores_form_and_list_rows_of_the_same_doctype(self):
		make_script("note-record-script").insert()
		make_script("note-form-script", view="Form", script="frappe.ui.form.on('Note', {})").insert()
		make_script("note-list-script", view="List", script="frappe.listview_settings['Note'] = {}").insert()

		self.assertEqual(script_names(), ["note-record-script"])

	def test_record_rows_are_invisible_to_desk_v1(self):
		make_script("note-record-script", script="export default { onRefresh() {} }").insert()
		frappe.clear_cache(doctype="Note")

		meta = get_meta("Note")
		self.assertNotIn("export default", meta.get("__custom_js") or "")
		self.assertNotIn("export default", meta.get("__custom_list_js") or "")

	def test_rejects_an_unknown_view(self):
		self.assertRaises(frappe.ValidationError, get_client_scripts, "Note", "List")

	def test_rejects_a_doctype_filter_posing_as_a_name(self):
		make_script("note-script").insert()
		self.assertRaises(frappe.FrappeTypeError, get_client_scripts, ["!=", ""], "Record")

	def test_reports_write_access_for_the_toast_gate(self):
		self.assertTrue(get_client_scripts("Note", "Record")["can_write"])


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
		before = frappe.db.get_value("Client Script", "a-note-script", "modified")
		reorder("Note", "Record", ["c-note-script", "b-note-script", "a-note-script"])

		self.assertEqual(frappe.db.get_value("Client Script", "a-note-script", "modified"), before)

	def test_tolerates_a_name_the_list_had_not_seen_yet(self):
		frappe.db.set_value("Client Script", "c-note-script", "run_order", 9, update_modified=False)
		reorder("Note", "Record", ["b-note-script", "a-note-script"])

		self.assertEqual(run_order("b-note-script"), 1)
		self.assertEqual(run_order("a-note-script"), 2)
		self.assertEqual(run_order("c-note-script"), 9)

	def test_rejects_a_name_from_another_doctypes_list(self):
		make_script("todo-script", dt="ToDo").insert()

		with self.assertRaises(frappe.ValidationError):
			reorder("Note", "Record", ["a-note-script", "todo-script"])

	def test_rejects_a_name_from_another_view(self):
		make_script("note-form-script", view="Form", script="frappe.ui.form.on('Note', {})").insert()

		with self.assertRaises(frappe.ValidationError):
			reorder("Note", "Record", ["a-note-script", "note-form-script"])

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
		with self.assertRaises(frappe.FrappeTypeError):
			reorder("Note", "Record", [["!=", ""]])

	def test_refuses_an_author_without_write_on_client_script(self):
		frappe.set_user(make_user("client-script-reader@example.com", ["Desk User"]))

		with self.assertRaises(frappe.PermissionError):
			reorder("Note", "Record", ["c-note-script", "a-note-script", "b-note-script"])

	def test_does_not_renumber_when_one_name_is_bad(self):
		with self.assertRaises(frappe.ValidationError):
			reorder("Note", "Record", ["a-note-script", "no-such-script"])

		self.assertEqual(run_order("a-note-script"), 0)


class TestUnknownClassWarning(IntegrationTestCase):
	def setUp(self):
		frappe.clear_messages()

	def tearDown(self):
		frappe.db.rollback()

	def save_with_class_list(self, script, class_list, name="styled-note-script"):
		path = os.path.join(self.class_list_dir.name, "classes.json")
		if class_list is None:
			if os.path.exists(path):
				os.remove(path)
		else:
			with open(path, "w") as file:
				json.dump(class_list, file)
		with patch.object(client_script, "class_list_path", return_value=path):
			make_script(name, script=script).insert()
		return [row["message"] for row in frappe.get_message_log()]

	def test_names_only_the_class_with_no_rule(self):
		script = "page.body.add({ html: '<div class=\"p-3 rounded-lg\">Late</div>' })"
		messages = self.save_with_class_list(script, ["p-3"])

		self.assertEqual(len(messages), 1)
		self.assertIn("rounded-lg", messages[0])
		self.assertNotIn("p-3", messages[0])

	def test_reads_class_keys_and_class_list_calls_but_not_prose(self):
		script = """
			page.header.add({ props: { class: `mt-2 ${size}` } })
			el.classList.add('hidden', 'pt-1')
			page.toast('a read-only follow-up')
		"""
		messages = self.save_with_class_list(script, ["hidden"])

		self.assertEqual(len(messages), 1)
		self.assertIn("mt-2, pt-1", messages[0])
		self.assertNotIn("read-only", messages[0])

	def test_reads_an_escaped_attribute_and_an_arbitrary_value_whole(self):
		script = 'page.body.add({ html: "<div class=\\"text-[#fff] p-3\\">" })'
		messages = self.save_with_class_list(script, ["p-3"])

		self.assertEqual(len(messages), 1)
		self.assertIn("text-[#fff]", messages[0])

	def test_is_silent_with_a_class_list_of_the_wrong_shape(self):
		script = "page.body.add({ html: '<div class=\"rounded-lg\">Late</div>' })"
		self.assertEqual(self.save_with_class_list(script, {"a": 1}, name="object-list-script"), [])
		self.assertEqual(self.save_with_class_list(script, None, name="null-list-script"), [])

	def test_stays_quiet_when_only_enabled_changes(self):
		script = "page.body.add({ html: '<div class=\"rounded-lg\">Late</div>' })"
		self.save_with_class_list(script, [])
		frappe.clear_messages()
		doc = frappe.get_doc("Client Script", "styled-note-script")
		doc.enabled = 0
		with patch.object(client_script, "read_class_list", return_value=set()):
			doc.save()
		self.assertEqual(frappe.get_message_log(), [])

	def test_is_silent_without_a_class_list(self):
		script = "page.body.add({ html: '<div class=\"rounded-lg\">Late</div>' })"
		self.assertEqual(self.save_with_class_list(script, None), [])

	def test_is_silent_for_a_form_view_script(self):
		script = "frappe.ui.form.on('Note', { refresh(frm) { $('<div class=\"rounded-lg\">') } })"
		with patch.object(client_script, "read_class_list", return_value=set()):
			make_script("form-note-script", script=script, view="Form").insert()
		self.assertEqual(frappe.get_message_log(), [])

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.class_list_dir = tempfile.TemporaryDirectory()

	@classmethod
	def tearDownClass(cls):
		cls.class_list_dir.cleanup()
		super().tearDownClass()
