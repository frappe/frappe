# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json
import os
import subprocess
import tempfile
from unittest.mock import patch

import frappe
from frappe.custom.doctype.client_script import client_script
from frappe.custom.doctype.client_script.client_script import (
	CompilerUnavailable,
	get_client_scripts,
	reorder,
)
from frappe.desk.form.meta import get_meta
from frappe.exceptions import TemplateCompileError
from frappe.modules.import_file import import_doc
from frappe.tests import IntegrationTestCase
from frappe.tests.test_api import FrappeAPITestCase

GOOD_TEMPLATE = 'export default {\n  name: "Greeting",\n  template: `<p>{{ __("Hello") }}</p>`,\n}\n'
# `Nope` is in no `components:` list, so the names check fails at line 3.
BAD_TEMPLATE = 'export default {\n  name: "Broken",\n  template: `<Nope />`,\n}\n'
H_SCRIPT = 'import { h } from "vue";\nexport default { render: () => h("p", "Hello") };\n'


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


def import_script(name, script, data_import=True, in_migrate=True):
	"""A fixture sync in `bench migrate`; `data_import=False` is a Package Import, `in_migrate=False` a Data Import."""
	docdict = {"doctype": "Client Script", "name": name, "dt": "Note", "view": "Record", "enabled": 1}
	frappe.flags.in_migrate = in_migrate
	try:
		return import_doc({**docdict, "script": script}, data_import=data_import)
	finally:
		frappe.flags.in_migrate = False


def fetched(name, dt="Note"):
	return next(row for row in get_client_scripts(dt, "Record")["scripts"] if row["name"] == name)


def compile_calls(run):
	return [call for call in run.call_args_list if "--key-parts" not in call.args[0]]


def logged(name):
	return frappe.db.exists("Error Log", {"reference_doctype": "Client Script", "reference_name": name})


class TestTemplateCompile(IntegrationTestCase):
	def setUp(self):
		frappe.cache.delete_keys(client_script.COMPILED_COPY)
		client_script.compiler_keys.clear()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def counting_node(self):
		return patch.object(client_script.subprocess, "run", wraps=subprocess.run)

	def test_a_bad_template_blocks_the_save_with_code_errors(self):
		with self.assertRaises(TemplateCompileError) as caught:
			make_script("bad-template", script=BAD_TEMPLATE).insert()

		[error] = caught.exception.code_errors
		self.assertEqual((error["field"], error["line"]), ("script", 3))
		self.assertTrue(error["column"] > 0 and error["message"])
		self.assertFalse(frappe.db.exists("Client Script", "bad-template"))

	def test_a_good_template_saves_and_the_page_gets_the_compiled_copy(self):
		make_script("good-template", script=GOOD_TEMPLATE).insert()
		frappe.set_user(make_user("client-script-reader@example.com", ["Desk User"]))

		row = fetched("good-template")
		self.assertNotIn("error", row)
		self.assertNotIn("template:", row["script"])
		self.assertTrue(row["script"].startswith("import { "))
		# Every line keeps its number, so a stack trace points at the author's line.
		self.assertEqual(row["script"].count("\n"), GOOD_TEMPLATE.count("\n"))
		self.assertEqual(frappe.db.get_value("Client Script", "good-template", "script"), GOOD_TEMPLATE)

	def test_a_fixture_import_keeps_the_record_and_logs(self):
		import_script("fixture-template", BAD_TEMPLATE)

		self.assertTrue(frappe.db.exists("Client Script", "fixture-template"))
		self.assertTrue(logged("fixture-template"))

	def test_a_package_import_keeps_the_record_and_logs(self):
		import_script("package-template", BAD_TEMPLATE, data_import=False, in_migrate=False)

		self.assertTrue(frappe.db.exists("Client Script", "package-template"))
		self.assertTrue(logged("package-template"))

	def test_a_data_import_blocks_like_the_form(self):
		with self.assertRaises(TemplateCompileError):
			import_script("uploaded-template", BAD_TEMPLATE, in_migrate=False)

	def test_an_unchanged_resave_runs_no_node(self):
		script = make_script("good-template", script=GOOD_TEMPLATE).insert()
		frappe.cache.delete_keys(client_script.COMPILED_COPY)

		with self.counting_node() as run:
			script.enabled = 0
			script.save()
		self.assertEqual(run.call_count, 0)

	def test_moving_a_script_to_the_record_view_compiles_it(self):
		script = make_script("form-template", view="Form", script=BAD_TEMPLATE).insert()

		script.view = "Record"
		with self.assertRaises(TemplateCompileError):
			script.save()

	def test_a_changed_compiler_file_asks_node_for_the_key_parts_again(self):
		make_script("good-template", script=GOOD_TEMPLATE).insert()
		stamp = client_script.compiler_stamp()

		with self.counting_node() as run:
			with patch.object(client_script, "compiler_stamp", return_value=(*stamp, ("moved", 1, 1))):
				fetched("good-template")
		self.assertEqual(len(run.call_args_list) - len(compile_calls(run)), 1)

	def test_a_compiler_that_fails_sends_an_error_row_without_its_output(self):
		import_script("fixture-template", GOOD_TEMPLATE)
		frappe.cache.delete_keys(client_script.COMPILED_COPY)
		failed = subprocess.CompletedProcess([], 1, "", "Error: Cannot find module '/srv/bench/x.mjs'")

		with patch.object(client_script.subprocess, "run", return_value=failed):
			with patch.object(client_script.frappe, "log_error") as log_error:
				row = fetched("fixture-template")
		self.assertEqual(row["script"], "")
		self.assertIn("The Error Log has the details", row["error"])
		self.assertNotIn("/srv/bench", row["error"])
		self.assertIn("/srv/bench", log_error.call_args.kwargs["message"])

	def test_a_failing_compiler_still_sends_the_cached_copies(self):
		make_script("good-template", script=GOOD_TEMPLATE).insert()
		import_script("fixture-template", GOOD_TEMPLATE.replace("Hello", "Bye"))
		frappe.cache.delete_value(
			client_script.compiled_copy_key(
				client_script.compiler_key(), GOOD_TEMPLATE.replace("Hello", "Bye")
			)
		)
		timeout = subprocess.TimeoutExpired("node", client_script.COMPILE_TIMEOUT)

		with patch.object(client_script.subprocess, "run", side_effect=timeout):
			cached, failed = fetched("good-template"), fetched("fixture-template")
		self.assertNotIn("error", cached)
		self.assertTrue(cached["script"].startswith("import { "))
		self.assertIn("did not finish", failed["error"])

	def test_a_compiler_that_hangs_sends_an_error_row(self):
		import_script("fixture-template", GOOD_TEMPLATE)
		frappe.cache.delete_keys(client_script.COMPILED_COPY)
		timeout = subprocess.TimeoutExpired("node", client_script.COMPILE_TIMEOUT)

		with patch.object(client_script.subprocess, "run", side_effect=timeout):
			row = fetched("fixture-template")
		self.assertEqual(row["script"], "")
		self.assertIn("did not finish", row["error"])

	def test_a_fetch_sends_a_failed_script_as_an_error_row_and_the_others_whole(self):
		import_script("fixture-template", BAD_TEMPLATE)
		make_script("h-script", script=H_SCRIPT).insert()
		frappe.set_user(make_user("client-script-reader@example.com", ["Desk User"]))

		row = fetched("fixture-template")
		self.assertEqual(row["script"], "")
		self.assertRegex(row["error"], r"^Line 3, column \d+: .+")
		self.assertEqual(fetched("h-script"), {"name": "h-script", "script": H_SCRIPT})

	def test_a_cache_hit_runs_no_node(self):
		make_script("good-template", script=GOOD_TEMPLATE).insert()

		with self.counting_node() as run:
			fetched("good-template")
		self.assertEqual(run.call_count, 0)

	def test_a_failed_compile_is_cached(self):
		import_script("fixture-template", BAD_TEMPLATE)

		with self.counting_node() as run:
			first, second = fetched("fixture-template"), fetched("fixture-template")
		self.assertEqual(run.call_count, 0)
		self.assertEqual(first, second)

	def test_one_node_call_compiles_every_script_of_the_doctype(self):
		make_script("good-template", script=GOOD_TEMPLATE).insert()
		import_script("fixture-template", BAD_TEMPLATE)
		frappe.cache.delete_keys(client_script.COMPILED_COPY)

		with self.counting_node() as run:
			get_client_scripts("Note", "Record")
		self.assertEqual(len(compile_calls(run)), 1)

	def test_a_script_without_the_word_never_runs_node(self):
		with self.counting_node() as run:
			make_script("h-script", script=H_SCRIPT).insert()
			fetched("h-script")
		self.assertEqual(run.call_count, 0)

	def test_a_quoted_template_key_in_plain_data_saves_unchanged(self):
		script = 'export default { onLoad() { return { "template": "Invoice" }; } };\n'
		make_script("plain-data", script=script).insert()

		self.assertEqual(fetched("plain-data")["script"], script)

	def test_a_missing_node_gives_a_clear_message_on_save(self):
		with patch.object(client_script.shutil, "which", return_value=None):
			with self.assertRaisesRegex(CompilerUnavailable, "Node.js is not installed"):
				make_script("good-template", script=GOOD_TEMPLATE).insert()

	def test_a_missing_node_sends_an_error_row_on_fetch(self):
		with patch.object(client_script.shutil, "which", return_value=None):
			import_script("fixture-template", GOOD_TEMPLATE)
			row = fetched("fixture-template")
		self.assertEqual(row["script"], "")
		self.assertIn("Node.js is not installed", row["error"])

	def test_code_built_from_a_string_fails_the_compile_and_runs_nothing(self):
		with tempfile.TemporaryDirectory() as folder:
			entry, marker = os.path.join(folder, "entry.mjs"), os.path.join(folder, "ran")
			with open(entry, "w") as file:
				file.write(
					'import { writeFileSync } from "node:fs";\n'
					f"new Function(`writeFileSync({json.dumps(marker)}, '')`)();\n"
				)
			with patch.object(client_script, "COMPILER_ENTRY", entry):
				with patch.object(client_script.frappe, "log_error") as log_error:
					with self.assertRaises(CompilerUnavailable):
						client_script.run_compiler("--key-parts")
			self.assertFalse(os.path.exists(marker))
		self.assertIn("Code generation from strings disallowed", log_error.call_args.kwargs["message"])


class TestTemplateCompileErrorEntry(FrappeAPITestCase):
	version = "v2"

	def test_the_v2_error_entry_carries_code_errors(self):
		frappe.cache.delete_keys(client_script.COMPILED_COPY)
		data = {"dt": "Note", "view": "Record", "enabled": 1, "script": BAD_TEMPLATE, "sid": self.sid}
		response = self.post(self.resource("Client Script"), {"__newname": "api-bad-template", **data})

		self.assertEqual(response.status_code, 417)
		[entry] = response.json["errors"]
		self.assertEqual(entry["type"], "TemplateCompileError")
		[error] = entry["code_errors"]
		self.assertEqual((error["field"], error["line"]), ("script", 3))
