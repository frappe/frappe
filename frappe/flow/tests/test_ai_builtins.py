# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
from unittest.mock import patch

import frappe
from frappe.desk.doctype.todo.todo import ToDo
from frappe.tests import IntegrationTestCase

from flow import ToolContext
from flow.patches.rename_read_tools import execute as rename_read_tools
from flow.tools.builtins import (
	BUILTIN_TOOLS,
	create,
	delete,
	describe,
	execute,
	find_doctypes,
	read_records,
	run_action,
	run_report,
	sync_builtin_tools,
	update,
)

CTX = ToolContext(session_id="test", agent="Test Agent", user="Administrator")

REPORT_SCRIPT = """
if not filters.company:
	frappe.throw("Company is mandatory")
columns = [
	{"fieldname": "item", "label": "Item", "fieldtype": "Data"},
	{"fieldname": "qty", "label": "Qty", "fieldtype": "Int"},
	{"fieldname": "note", "label": "Note", "fieldtype": "Data", "hidden": 1},
]
rows = [{"item": f"Item {i}", "qty": i, "note": "x"} for i in range(1, 26)]
data = [columns, rows if filters.company == "Acme" else []]
"""

REPORT_JS = """frappe.query_reports["Flow Report Probe"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", reqd: 1 },
		{ fieldname: "item", label: __("Item"), fieldtype: "Data" },
	],
};"""


class TestFindDoctypes(IntegrationTestCase):
	def test_search_matches_by_keyword(self):
		names = {r["name"] for r in find_doctypes(search="ToDo", ctx=CTX)}
		self.assertIn("ToDo", names)

	def test_filters_by_module(self):
		rows = find_doctypes(module="Core", limit=200, ctx=CTX)
		self.assertTrue(rows)
		self.assertTrue(all(r["module"] == "Core" for r in rows))

	def test_excludes_child_tables(self):
		names = {r["name"] for r in find_doctypes(search="Role", limit=200, ctx=CTX)}
		self.assertIn("Role", names)
		self.assertNotIn("Has Role", names)  # a child table that also matches "Role"

	def test_includes_single_doctypes(self):
		names = {r["name"] for r in find_doctypes(search="System Settings", limit=200, ctx=CTX)}
		self.assertIn("System Settings", names)  # a single DocType

	def test_respects_read_permission(self):
		frappe.set_user("Guest")
		try:
			names = {r["name"] for r in find_doctypes(search="User", limit=200, ctx=CTX)}
			self.assertNotIn("User", names)
		finally:
			frappe.set_user("Administrator")


class TestDescribe(IntegrationTestCase):
	def test_returns_fields_and_permissions(self):
		result = describe(doctype="ToDo", ctx=CTX)

		self.assertEqual(result["doctype"], "ToDo")
		fieldnames = {f["fieldname"] for f in result["fields"]}
		self.assertIn("description", fieldnames)
		self.assertEqual(set(result["permissions"]), {"read", "write", "create", "delete"})

	def test_excludes_layout_fields(self):
		result = describe(doctype="ToDo", ctx=CTX)
		types = {f["type"] for f in result["fields"]}
		self.assertNotIn("Section Break", types)
		self.assertNotIn("Column Break", types)

	def test_permission_denied_raises(self):
		frappe.set_user("Guest")
		try:
			with self.assertRaises(PermissionError):
				describe(doctype="User", ctx=CTX)
		finally:
			frappe.set_user("Administrator")

	def test_describes_a_child_table(self):
		frappe.set_user(_user("flow-describe-probe@example.com"))
		try:
			result = describe(doctype="Contact Phone", ctx=CTX)
		finally:
			frappe.set_user("Administrator")

		self.assertIn("phone", {f["fieldname"] for f in result["fields"]})
		self.assertTrue(result["permissions"]["read"])


class TestReadRecords(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_reads_matching_records(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "ai builtin read probe"}).insert()

		rows = read_records(doctype="ToDo", filters={"description": "ai builtin read probe"}, ctx=CTX)

		self.assertEqual([r["name"] for r in rows], [todo.name])

	def test_limit_is_capped(self):
		rows = read_records(doctype="DocType", limit=10_000, ctx=CTX)
		self.assertLessEqual(len(rows), 200)

	def test_returns_requested_fields(self):
		frappe.get_doc({"doctype": "ToDo", "description": "fields probe"}).insert()
		rows = read_records(
			doctype="ToDo",
			filters={"description": "fields probe"},
			fields=["name", "description"],
			ctx=CTX,
		)
		self.assertEqual(rows[0]["description"], "fields probe")

	def test_reads_a_single(self):
		# CI's site skips the setup wizard, which sets the time zone
		frappe.db.set_single_value("System Settings", "time_zone", "Asia/Kolkata")

		rows = read_records(doctype="System Settings", fields=["time_zone"], ctx=CTX)
		[values] = read_records(doctype="System Settings", ctx=CTX)

		self.assertEqual(rows, [{"time_zone": "Asia/Kolkata"}])
		self.assertEqual((values["name"], values["time_zone"]), ("System Settings", "Asia/Kolkata"))

	def test_single_is_returned_only_when_it_matches_the_filters(self):
		frappe.db.set_single_value("System Settings", "time_zone", "Asia/Kolkata")

		missed = read_records(doctype="System Settings", filters={"time_zone": "UTC"}, ctx=CTX)
		matched = read_records(
			doctype="System Settings", filters={"time_zone": "Asia/Kolkata"}, fields=["name"], ctx=CTX
		)

		self.assertEqual(missed, [])
		self.assertEqual(matched, [{"name": "System Settings"}])

	def test_single_needs_read_permission(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			read_records(doctype="System Settings", ctx=CTX)

	def test_reads_child_rows_of_parents_the_user_can_read(self):
		user = _user("flow-child-probe@example.com")  # reads only the Contacts they own
		mine = _contact_with_phone(owner=user)
		_contact_with_phone(owner="Administrator")
		frappe.set_user(user)

		rows = read_records(doctype="Contact Phone", fields=["parent"], ctx=CTX)

		self.assertEqual({r["parent"] for r in rows}, {mine})

	def test_child_table_of_several_doctypes_needs_parent_doctype(self):
		with self.assertRaises(ValueError) as caught:
			read_records(doctype="Has Role", ctx=CTX)

		self.assertIn("pass parent_doctype, one of:", str(caught.exception))
		self.assertIn("Role Profile", str(caught.exception))

	def test_a_parent_doctype_the_table_isnt_in_lists_its_parents(self):
		with self.assertRaises(ValueError) as caught:
			read_records(doctype="Has Role", parent_doctype="ToDo", ctx=CTX)

		self.assertIn("Role Profile", str(caught.exception))

	def test_child_rows_come_only_from_the_given_parent_doctype(self):
		user = _user("flow-collision-probe@example.com")
		frappe.get_doc("User", user).add_roles("System Manager")
		# a Role Profile named like the user, whose role rows match the user by name
		frappe.get_doc(
			{"doctype": "Role Profile", "role_profile": user, "roles": [{"role": "System Manager"}]}
		).insert()

		rows = read_records(
			doctype="Has Role",
			filters={"parent": user},
			fields=["parenttype"],
			parent_doctype="User",
			ctx=CTX,
		)
		# execute's sandbox calls the function unchecked, where filters can be a list
		listed = read_records.func(
			doctype="Has Role",
			filters=[["parent", "=", user]],
			fields=["parenttype"],
			parent_doctype="User",
			ctx=CTX,
		)

		self.assertEqual({r["parenttype"] for r in rows}, {"User"})
		self.assertEqual({r["parenttype"] for r in listed}, {"User"})


class TestRunReport(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		cls.enterClassContext(cls.enable_safe_exec())
		super().setUpClass()

	def setUp(self):
		self.report = self.make_report(
			"Flow Report Probe",
			"Script Report",
			report_script=REPORT_SCRIPT,
			javascript=REPORT_JS,
			filters=[{"fieldname": "warehouse", "label": "Warehouse", "fieldtype": "Data", "mandatory": 1}],
		)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_returns_shown_columns_capped_rows_and_count(self):
		result = run_report(report_name=self.report.name, filters={"company": "Acme"}, limit=10, ctx=CTX)

		self.assertEqual(
			result["columns"], [{"fieldname": "item", "label": "Item"}, {"fieldname": "qty", "label": "Qty"}]
		)
		self.assertEqual(result["rows"][0], {"item": "Item 1", "qty": 1})
		self.assertEqual(len(result["rows"]), 10)
		self.assertEqual(result["row_count"], 25)
		self.assertNotIn("total_row", result)
		self.assertNotIn("available_filters", result)

	def test_total_row_is_kept_past_the_cap(self):
		self.report.db_set("add_total_row", 1)

		result = run_report(report_name=self.report.name, filters={"company": "Acme"}, limit=10, ctx=CTX)

		self.assertEqual(result["total_row"], {"item": "Total", "qty": 325})
		self.assertEqual(result["row_count"], 25)
		# a cut keeps the head, so the count and total come before the rows
		self.assertEqual(list(result), ["columns", "row_count", "total_row", "rows"])

		rows = run_report(report_name=self.report.name, filters={"company": "Acme"}, limit=200, ctx=CTX)[
			"rows"
		]
		self.assertEqual((len(rows), rows[-1]), (25, {"item": "Item 25", "qty": 25}))

	def test_failed_run_lists_the_filters(self):
		# frappe's failure log survives the rollback
		with patch("frappe.log_error"), self.assertRaises(ValueError) as caught:
			run_report(report_name=self.report.name, ctx=CTX)

		self.assertIn("Company is mandatory", str(caught.exception))
		self.assertIn("(* = required) warehouse*, company*, item", str(caught.exception))

	def test_a_query_reports_own_error_is_kept(self):
		def fail(*args, **kwargs):
			try:
				raise KeyError("owner")
			except KeyError:  # frappe's failure log can't write in the report's read-only transaction
				raise frappe.InReadOnlyMode("Site is running in read only mode")

		with patch("frappe.desk.query_report.run", side_effect=fail), self.assertRaises(ValueError) as caught:
			run_report(report_name=self.report.name, filters={"company": "Acme"}, ctx=CTX)
		self.assertTrue(str(caught.exception).startswith("'owner'\n"))

	def test_empty_run_lists_the_filters(self):
		result = run_report(report_name=self.report.name, filters={"company": "Other"}, ctx=CTX)

		self.assertEqual(result["row_count"], 0)
		self.assertEqual(result["available_filters"], "(* = required) warehouse*, company*, item")

	def test_report_that_returns_nothing_is_empty(self):
		self.report.db_set("report_script", "pass")

		result = run_report(report_name=self.report.name, filters={"company": "Acme"}, ctx=CTX)

		self.assertEqual(result["rows"], [])
		self.assertIn("available_filters", result)

	def test_report_builder_is_refused(self):
		builder = self.make_report("Flow Builder Probe", "Report Builder")

		with self.assertRaises(ValueError) as caught:
			run_report(report_name=builder.name, ctx=CTX)
		self.assertIn("read_records", str(caught.exception))

	def test_query_report_runs(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "query report probe"}).insert()
		query = self.make_report(
			"Flow Query Probe",
			"Query Report",
			query='select name as "ToDo:Link/ToDo:120", description as "Description:Data:200" '
			"from tabToDo where description = %(description)s",
		)

		# a query report opens its own transaction; keep it in the test's
		with patch.object(frappe.db, "begin"), patch.object(frappe.db, "rollback"):
			result = run_report(
				report_name=query.name, filters={"description": "query report probe"}, ctx=CTX
			)

		self.assertEqual(
			result["columns"],
			[{"fieldname": "todo", "label": "ToDo"}, {"fieldname": "description", "label": "Description"}],
		)
		self.assertEqual(result["rows"], [{"todo": todo.name, "description": "query report probe"}])

	def test_query_report_needs_its_sql_filters_first(self):
		# never run it here: a query report opens its own transaction
		query = self.make_report(
			"Flow Query Probe", "Query Report", query="select name from tabToDo where owner = %(owner)s"
		)

		with self.assertRaises(ValueError) as caught:
			run_report(report_name=query.name, ctx=CTX)
		self.assertEqual(str(caught.exception), "Missing filters: owner")

	def test_custom_report_uses_its_saved_filters(self):
		query = self.make_report(
			"Flow Query Probe", "Query Report", query="select name from tabToDo where owner = %(owner)s"
		)
		custom = self.make_report(
			"Flow Custom Probe",
			"Custom Report",
			reference_report=query.name,
			json=json.dumps({"filters": {"owner": "Administrator"}}),
		)

		with patch("frappe.desk.query_report.run", return_value={"columns": [], "result": []}) as ran:
			run_report(report_name=custom.name, ctx=CTX)
		ran.assert_called_once()

	def test_only_a_prepared_report_runs_in_the_background(self):
		args = {"report_name": self.report.name}
		self.assertFalse(run_report.background(args))
		self.report.db_set("prepared_report", 1)
		self.assertTrue(run_report.background(args))
		self.assertFalse(run_report.background({}))

	def test_permission_denied_raises(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			run_report(report_name=self.report.name, filters={"company": "Acme"}, ctx=CTX)

	def make_report(self, name: str, report_type: str, **values):
		return frappe.get_doc(
			{
				"doctype": "Report",
				"report_name": name,
				"ref_doctype": "ToDo",
				"report_type": report_type,
				"is_standard": "No",
				**values,
			}
		).insert()


class TestExecute(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		cls.enterClassContext(cls.enable_safe_exec())
		super().setUpClass()

	def tearDown(self):
		frappe.db.rollback()

	def test_returns_result_variable(self):
		self.assertEqual(execute(code="result = 1 + 1", description="Add two numbers", ctx=CTX), 2)

	def test_no_result_returns_none(self):
		self.assertIsNone(execute(code="x = 5", description="Set a variable", ctx=CTX))

	def test_can_read_via_frappe(self):
		count = execute(code="result = frappe.db.count('DocType')", description="Count doctypes", ctx=CTX)
		self.assertIsInstance(count, int)

	def test_imports_are_blocked(self):
		with self.assertRaises(Exception):
			execute(code="import os\nresult = os.getcwd()", description="Get working directory", ctx=CTX)


class TestCreate(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_requires_confirmation(self):
		self.assertTrue(create.requires_confirmation)

	def test_creates_doc_with_values(self):
		result = create(doctype="ToDo", records=[{"description": "ai create probe"}], ctx=CTX)

		self.assertEqual(result["doctype"], "ToDo")
		self.assertEqual(len(result["created"]), 1)
		name = result["created"][0]
		self.assertTrue(frappe.db.exists("ToDo", name))
		self.assertEqual(frappe.db.get_value("ToDo", name, "description"), "ai create probe")

	def test_permission_denied_raises(self):
		frappe.set_user("Guest")
		with self.assertRaises(PermissionError):
			create(doctype="User", records=[{"email": "x@example.com"}], ctx=CTX)

	def test_a_missing_required_field_fails_the_call(self):
		# ToDo.description is mandatory
		with self.assertRaisesRegex(ValueError, "Record 1 of 1"):
			create(doctype="ToDo", records=[{}], ctx=CTX)

	def test_one_failed_record_creates_none(self):
		records = [{"description": "ai create works"}, {"description": "ai create fails"}]
		with (
			_todo_hook_fails("after_insert", "ai create fails"),
			self.assertRaisesRegex(ValueError, "Record 2 of 2: hook failed\nNothing was saved."),
		):
			create(doctype="ToDo", records=records, ctx=CTX)

		self.assertFalse(
			frappe.db.exists("ToDo", {"description": ["in", ["ai create works", "ai create fails"]]})
		)


class TestUpdate(IntegrationTestCase):
	def setUp(self):
		self.todo = frappe.get_doc({"doctype": "ToDo", "description": "ai update probe"}).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_requires_confirmation(self):
		self.assertTrue(update.requires_confirmation)

	def test_modifies_doc_fields(self):
		result = update(doctype="ToDo", names=[self.todo.name], values={"status": "Closed"}, ctx=CTX)

		self.assertEqual(result["updated"], [self.todo.name])
		self.assertEqual(frappe.db.get_value("ToDo", self.todo.name, "status"), "Closed")

	def test_an_invalid_value_fails_the_call(self):
		# Status is a Select field with a fixed set
		with self.assertRaisesRegex(ValueError, self.todo.name):
			update(doctype="ToDo", names=[self.todo.name], values={"status": "Not A Real Status"}, ctx=CTX)

	def test_a_missing_record_fails_the_call(self):
		with self.assertRaisesRegex(ValueError, "does-not-exist"):
			update(doctype="ToDo", names=["does-not-exist"], values={"status": "Closed"}, ctx=CTX)

	def test_permission_denied_fails_the_call(self):
		frappe.set_user("Guest")
		with self.assertRaisesRegex(ValueError, "No permission"):
			update(doctype="ToDo", names=[self.todo.name], values={"status": "Closed"}, ctx=CTX)

	def test_one_failed_record_changes_none(self):
		failing = frappe.get_doc({"doctype": "ToDo", "description": "ai update fails"}).insert()
		names = [self.todo.name, failing.name]
		with (
			_todo_hook_fails("on_update", "ai update fails"),
			self.assertRaisesRegex(ValueError, f"{failing.name}: hook failed\nNothing was saved."),
		):
			update(doctype="ToDo", names=names, values={"status": "Closed"}, ctx=CTX)

		self.assertEqual(frappe.get_all("ToDo", {"name": ["in", names]}, pluck="status"), ["Open", "Open"])

	def test_a_lost_savepoint_is_reported(self):
		def end_savepoint_then_fail(doc, *args, **kwargs):
			frappe.db.release_savepoint("flow_batch")
			raise frappe.ValidationError("after the savepoint")

		with (
			patch.object(ToDo, "on_update", end_savepoint_then_fail),
			self.assertRaisesRegex(
				ValueError, "after the savepoint\nSome earlier changes may already be committed"
			),
		):
			update(doctype="ToDo", names=[self.todo.name], values={"status": "Closed"}, ctx=CTX)


class TestDelete(IntegrationTestCase):
	def setUp(self):
		self.todo = frappe.get_doc({"doctype": "ToDo", "description": "ai delete probe"}).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_requires_confirmation(self):
		self.assertTrue(delete.requires_confirmation)

	def test_removes_doc(self):
		result = delete(doctype="ToDo", names=[self.todo.name], ctx=CTX)

		self.assertEqual(result["deleted"], [self.todo.name])
		self.assertFalse(frappe.db.exists("ToDo", self.todo.name))

	def test_a_missing_record_fails_the_call(self):
		with self.assertRaisesRegex(ValueError, "does-not-exist"):
			delete(doctype="ToDo", names=["does-not-exist"], ctx=CTX)

	def test_permission_denied_fails_the_call(self):
		frappe.set_user("Guest")
		with self.assertRaisesRegex(ValueError, "No permission"):
			delete(doctype="ToDo", names=[self.todo.name], ctx=CTX)

	def test_one_failed_record_deletes_none(self):
		failing = frappe.get_doc({"doctype": "ToDo", "description": "ai delete fails"}).insert()
		names = [self.todo.name, failing.name]
		with (
			_todo_hook_fails("after_delete", "ai delete fails"),
			self.assertRaisesRegex(ValueError, f"{failing.name}: hook failed"),
		):
			delete(doctype="ToDo", names=names, ctx=CTX)

		self.assertEqual(frappe.db.count("ToDo", {"name": ["in", names]}), 2)


class TestRunAction(IntegrationTestCase):
	def setUp(self):
		self.todo = frappe.get_doc({"doctype": "ToDo", "description": "ai action probe"}).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_one_failed_record_changes_none(self):
		failing = frappe.get_doc({"doctype": "ToDo", "description": "ai action fails"}).insert()
		names = [self.todo.name, failing.name]
		with (
			_todo_hook_fails("on_discard", "ai action fails"),
			self.assertRaisesRegex(ValueError, f"{failing.name}: hook failed"),
		):
			run_action(doctype="ToDo", names=names, action="discard", ctx=CTX)

		self.assertEqual(frappe.get_all("ToDo", {"name": ["in", names]}, pluck="docstatus"), [0, 0])


class TestSyncBuiltinTools(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_creates_rows_for_all_builtins(self):
		sync_builtin_tools()
		for builtin in BUILTIN_TOOLS:
			self.assertTrue(frappe.db.exists("Flow Tool", builtin.name))

	def test_resolves_back_to_runtime_tool(self):
		sync_builtin_tools()
		doc = frappe.get_doc("Flow Tool", "describe")
		runtime = doc.to_tool()
		self.assertEqual(runtime.name, "describe")
		self.assertIn("doctype", runtime.parameters["properties"])

	def test_a_per_call_background_rule_stays_in_code(self):
		sync_builtin_tools()
		doc = frappe.get_doc("Flow Tool", "run_report")
		self.assertEqual(doc.background, 0)
		self.assertTrue(callable(doc.to_tool().background))

	def test_is_idempotent(self):
		sync_builtin_tools()
		sync_builtin_tools()
		count = frappe.db.count("Flow Tool", {"slug": "read"})
		self.assertEqual(count, 1)


class TestRenameReadTools(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_agents_keep_their_tools_under_the_new_names(self):
		model = frappe.get_doc(
			{"doctype": "Flow Model", "title": "Rename Model", "model_id": "openai/gpt-4o-mini", "enabled": 1}
		).insert()
		agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Rename Agent",
				"model": model.name,
				"instructions": "Be terse.",
			}
		).insert()
		# the old file tool row, as before the rename
		frappe.db.delete("Flow Tool", {"name": "read_file"})
		frappe.get_doc(
			{
				"doctype": "Flow Tool",
				"name": "read_file",
				"slug": "read_file",
				"title": "Read File",
				"type": "Imported",
				"import_path": "flow.tools.builtins.read_file",
				"is_system_generated": 1,
			}
		).db_insert()
		for tool in ("read", "read_file"):
			agent.append("tools", {"tool": tool}).db_insert()

		rename_read_tools()
		rename_read_tools()  # a second run changes nothing

		filters = {"parent": agent.name, "tool": ["like", "read%"]}
		self.assertEqual(
			frappe.get_all("Flow Agent Tool", filters, pluck="tool", order_by="idx"), ["read_records", "read"]
		)
		self.assertFalse(frappe.db.exists("Flow Tool", "read_file"))


def _user(email: str) -> str:
	"""A user with no roles, so permission checks apply."""
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": "Probe", "send_welcome_email": 0}
		).insert(ignore_permissions=True)
	return email


def _todo_hook_fails(hook: str, description: str):
	"""ToDo's `hook` raises for the ToDo with this description, after that record's write."""

	def fail(doc, *args, **kwargs):
		if doc.description == description:
			raise frappe.ValidationError("hook failed")

	return patch.object(ToDo, hook, fail, create=True)


def _contact_with_phone(owner: str) -> str:
	contact = frappe.get_doc(
		{"doctype": "Contact", "first_name": "Flow Probe", "phone_nos": [{"phone": "+1 555 0100"}]}
	).insert()
	frappe.db.set_value("Contact", contact.name, "owner", owner)
	return contact.name
