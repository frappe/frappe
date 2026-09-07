# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
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
